"""
自动化脚本管理 API
"""
import json
import logging
import time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.automation_script import AutomationScript
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.tasks.script_tasks import run_automation_script_task
from app.schemas.automation_script import (
    AutomationScriptCreate,
    AutomationScriptUpdate,
    AutomationScriptResponse,
    ScriptRunRequest,
)
from app.agents.script_generator import ScriptGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/scripts", tags=["自动化脚本"])


def _check_project_access(project_id: int, db: Session, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


@router.get("", response_model=List[AutomationScriptResponse])
def list_scripts(
    project_id: int,
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取脚本列表"""
    _check_project_access(project_id, db, current_user)
    query = db.query(AutomationScript).filter(AutomationScript.project_id == project_id)
    if status:
        query = query.filter(AutomationScript.status == status)
    if case_id:
        query = query.filter(AutomationScript.case_id == case_id)
    if keyword:
        query = query.filter(AutomationScript.name.contains(keyword))
    return query.order_by(AutomationScript.updated_at.desc()).all()


@router.get("/{script_id}", response_model=AutomationScriptResponse)
def get_script(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取脚本详情"""
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return script


@router.post("", response_model=AutomationScriptResponse, status_code=status.HTTP_201_CREATED)
def create_script(
    project_id: int,
    data: AutomationScriptCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建脚本（支持AI异步生成）"""
    _check_project_access(project_id, db, current_user)

    is_ai = data.ai_generate and bool(data.description)
    initial_content = data.script_content

    # AI生成模式下，名称可为空，先用临时名称占位，后台由AI生成真实名称
    script_name = data.name
    need_ai_name = is_ai and not script_name
    if not script_name:
        script_name = "AI生成脚本" if is_ai else "未命名脚本"

    if not initial_content:
        initial_content = ScriptGenerator.generate_template(data.target_url or "", script_name)

    script = AutomationScript(
        project_id=project_id,
        name=script_name,
        description=data.description or "",
        case_id=data.case_id,
        script_content=initial_content,
        script_type="ai_generated" if is_ai else (data.script_type or "manual"),
        target_url=data.target_url or "",
        language=data.language or "python",
        status="generating" if is_ai else (data.status or "active"),
        tags=data.tags or ("ai-generated" if is_ai else ""),
        created_by=current_user.id,
    )
    db.add(script)
    db.commit()
    db.refresh(script)

    # 异步AI生成脚本
    if is_ai:
        background_tasks.add_task(
            _generate_script_background,
            script_id=script.id,
            description=data.description or "",
            target_url=data.target_url or "",
            script_name=script_name,
            llm_config_id=data.llm_config_id,
            need_ai_name=need_ai_name,
        )

    return script


def _generate_script_background(
    script_id: int,
    description: str,
    target_url: str,
    script_name: str,
    llm_config_id: Optional[int] = None,
    need_ai_name: bool = False,
):
    """后台异步生成AI脚本"""
    import asyncio
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
        if not script:
            return

        script.status = "generating"
        db.commit()

        # 如果需要AI生成脚本名称，先生成名称
        final_name = script_name
        if need_ai_name:
            try:
                final_name = asyncio.run(
                    ScriptGenerator.generate_script_name(
                        description=description,
                        target_url=target_url,
                        llm_config_id=llm_config_id,
                        db_session=db,
                    )
                )
                script.name = final_name
                db.commit()
                logger.info(f"AI脚本名称生成完成: script_id={script_id}, name={final_name}")
            except Exception as e:
                logger.warning(f"AI生成脚本名称失败，使用默认名称: script_id={script_id}, error={e}")

        # 调用AI生成脚本内容
        generated_content = asyncio.run(
            ScriptGenerator.generate_with_ai(
                description=description,
                target_url=target_url,
                script_name=final_name,
                llm_config_id=llm_config_id,
                db_session=db,
            )
        )

        script.script_content = generated_content
        script.status = "active"
        script.version = (script.version or 1) + 1
        script.updated_at = china_now_naive()
        db.commit()
        logger.info(f"AI脚本生成完成: script_id={script_id}")

    except Exception as e:
        logger.error(f"AI脚本生成失败: script_id={script_id}, error={e}", exc_info=True)
        try:
            script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
            if script:
                script.status = "failed"
                script.description = f"{script.description}\n\n[AI生成失败: {str(e)[:200]}]"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.put("/{script_id}", response_model=AutomationScriptResponse)
def update_script(
    project_id: int,
    script_id: int,
    data: AutomationScriptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新脚本"""
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(script, key, value)
    script.version = (script.version or 1) + 1
    script.updated_at = china_now_naive()
    db.commit()
    db.refresh(script)
    return script


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_script(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除脚本"""
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    script.soft_delete()
    db.commit()


@router.post("/{script_id}/duplicate", response_model=AutomationScriptResponse)
def duplicate_script(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """复制脚本"""
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    new_script = AutomationScript(
        project_id=project_id,
        name=f"{script.name} (副本)",
        description=script.description or "",
        case_id=script.case_id,
        script_content=script.script_content,
        script_type=script.script_type,
        target_url=script.target_url,
        language=script.language,
        status="draft",
        tags=script.tags,
        created_by=current_user.id,
    )
    db.add(new_script)
    db.commit()
    db.refresh(new_script)
    return new_script


@router.get("/by-case/{case_id}", response_model=List[AutomationScriptResponse])
def get_scripts_by_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例关联的脚本列表"""
    _check_project_access(project_id, db, current_user)
    return db.query(AutomationScript).filter(
        AutomationScript.project_id == project_id,
        AutomationScript.case_id == case_id,
    ).order_by(AutomationScript.updated_at.desc()).all()


async def _run_script_background(
    run_id: int,
    script_id: int,
    project_id: int,
    script_content: str,
    script_name: str,
    target_url: str,
    auto_fix: bool,
    max_retries: int,
    params: Optional[dict] = None,
):
    """
    后台执行脚本，支持AI自动修复重试
    使用独立的数据库会话，避免阻塞主接口
    """
    from app.database import SessionLocal
    import asyncio

    db = SessionLocal()
    try:
        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
        if not run or not script:
            logger.error(f"后台执行失败: run={run_id} 或 script={script_id} 不存在")
            return

        # 参数替换
        def apply_params(content: str) -> str:
            if params:
                for key, value in params.items():
                    content = content.replace(f"{{{{{key}}}}}", str(value))
            return content

        current_content = apply_params(script_content)
        start_time = time.time()
        start_datetime = run.started_at or china_now_naive()
        error_msg = ""
        status_result = "passed"
        retry_count = 0
        exec_log = [
            {"action": "script_run", "detail": f"执行脚本: {script_name}", "timestamp": start_time, "status": "running", "script_id": script_id}
        ]

        # 同步执行脚本的函数（在线程池中运行）
        def _run_script_sync(content: str, sid: int) -> tuple[bool, str]:
            """在独立事件循环中执行脚本，返回 (是否成功, 错误信息)"""
            import asyncio as _asyncio
            try:
                local_vars = {}
                exec(compile(content, f"script_{sid}.py", "exec"), local_vars)

                if "run_test" in local_vars and callable(local_vars["run_test"]):
                    # 在线程的独立事件循环中执行异步函数
                    _asyncio.run(local_vars["run_test"]())
                else:
                    raise RuntimeError("脚本中未找到 run_test 函数")
                return True, ""
            except Exception as e:
                return False, str(e)

        # 执行脚本的异步函数（使用线程池）
        async def execute_script(content: str) -> tuple[bool, str]:
            """在线程池中执行脚本，不阻塞主事件循环"""
            import asyncio as _asyncio
            return await _asyncio.to_thread(_run_script_sync, content, script_id)

        # 首次执行
        success, error_msg = await execute_script(current_content)
        duration = time.time() - start_time

        if success:
            exec_log.append({
                "action": "result", "detail": f"执行成功，耗时: {duration:.2f}s",
                "timestamp": time.time(), "status": "passed", "duration": round(duration, 3)
            })
        else:
            # 执行失败，记录首次失败
            exec_log.append({
                "action": "result", "detail": f"第1次执行失败，耗时: {duration:.2f}s, 错误: {error_msg}",
                "timestamp": time.time(), "status": "failed", "duration": round(duration, 3),
                "error": error_msg, "attempt": 1
            })

            # 自动修复重试循环
            max_retries = max(0, max_retries)

            while not success and auto_fix and retry_count < max_retries:
                retry_count += 1
                logger.info(f"脚本 #{script_id} 执行失败，开始第 {retry_count} 次AI修复重试")
                exec_log.append({
                    "action": "ai_fix", "detail": f"调用AI修复脚本（第{retry_count}次）",
                    "timestamp": time.time(), "status": "running", "attempt": retry_count
                })

                try:
                    # 调用AI修复脚本
                    fixed_content = await ScriptGenerator.fix_script_with_ai(
                        script_content=current_content,
                        error_message=error_msg,
                        script_name=script_name,
                        target_url=target_url or "",
                        db_session=db,
                    )

                    if fixed_content == current_content:
                        exec_log.append({
                            "action": "ai_fix", "detail": "AI修复未产生变化，停止重试",
                            "timestamp": time.time(), "status": "skipped", "attempt": retry_count
                        })
                        break

                    current_content = fixed_content
                    exec_log.append({
                        "action": "ai_fix", "detail": f"AI修复完成，修复后脚本长度: {len(fixed_content)}",
                        "timestamp": time.time(), "status": "success", "attempt": retry_count
                    })

                    # 使用修复后的脚本重新执行
                    retry_start = time.time()
                    success, error_msg = await execute_script(current_content)
                    retry_duration = time.time() - retry_start

                    if success:
                        duration = time.time() - start_time
                        exec_log.append({
                            "action": "result", "detail": f"第{retry_count + 1}次执行成功（修复后），耗时: {retry_duration:.2f}s",
                            "timestamp": time.time(), "status": "passed", "duration": round(retry_duration, 3),
                            "attempt": retry_count + 1, "fixed": True
                        })
                        status_result = "passed"
                        error_msg = ""

                        # 修复成功后，更新脚本库中的脚本内容
                        try:
                            script.script_content = current_content
                            script.version = (script.version or 1) + 1
                            script.status = "active"
                            script.description = (script.description or "") + f"\n[自动修复] 执行失败后AI自动修复成功，版本升级至 v{script.version}"
                            db.commit()
                            exec_log.append({
                                "action": "script_updated", "detail": f"脚本已自动更新至 v{script.version}",
                                "timestamp": time.time(), "status": "success", "new_version": script.version
                            })
                            logger.info(f"脚本 #{script_id} 已自动修复并更新至 v{script.version}")
                        except Exception as update_e:
                            logger.warning(f"更新脚本库失败: {update_e}")
                            db.rollback()
                    else:
                        exec_log.append({
                            "action": "result", "detail": f"第{retry_count + 1}次执行失败（修复后），耗时: {retry_duration:.2f}s, 错误: {error_msg}",
                            "timestamp": time.time(), "status": "failed", "duration": round(retry_duration, 3),
                            "error": error_msg, "attempt": retry_count + 1, "fixed": True
                        })

                except Exception as fix_e:
                    error_msg = f"AI修复异常: {str(fix_e)}"
                    logger.error(f"AI修复脚本异常: {fix_e}", exc_info=True)
                    exec_log.append({
                        "action": "ai_fix", "detail": f"AI修复异常: {str(fix_e)}",
                        "timestamp": time.time(), "status": "failed", "attempt": retry_count
                    })
                    break

            if not success:
                status_result = "failed"
                duration = time.time() - start_time

        # 更新执行记录
        run.status = status_result
        run.error_message = error_msg
        run.duration = round(duration, 2)
        run.started_at = start_datetime
        run.completed_at = china_now_naive()
        run.execution_log = json.dumps(exec_log, ensure_ascii=False)
        db.commit()

        # 更新脚本统计
        script.total_runs = (script.total_runs or 0) + 1
        script.last_run_status = status_result
        script.last_run_at = china_now_naive()
        if status_result == "passed":
            script.pass_count = (script.pass_count or 0) + 1
        else:
            script.fail_count = (script.fail_count or 0) + 1
        db.commit()

        logger.info(f"脚本 #{script_id} 后台执行完成: status={status_result}, duration={duration:.2f}s, retry_count={retry_count}")

    except Exception as e:
        logger.error(f"后台执行脚本异常: {e}", exc_info=True)
        try:
            run = db.query(TestRun).filter(TestRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = f"后台执行异常: {str(e)}"
                run.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{script_id}/run")
async def run_script(
    project_id: int,
    script_id: int,
    req: ScriptRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    运行单个脚本（Celery 任务队列执行）
    立即返回 run_id，执行状态通过执行记录接口查询
    执行失败时支持自动调用AI修复脚本并重试
    Celery 不可用时自动降级到 BackgroundTasks
    """
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    # 创建执行记录
    run = TestRun(
        project_id=project_id,
        case_id=script.case_id,
        status="running",
        execution_log=json.dumps([{"action": "script_run", "detail": f"执行脚本: {script.name}（排队中）"}], ensure_ascii=False),
        executed_by=current_user.id,
        started_at=china_now_naive(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    task_kwargs = dict(
        run_id=run.id,
        script_id=script_id,
        project_id=project_id,
        script_content=script.script_content,
        script_name=script.name,
        target_url=script.target_url or "",
        auto_fix=req.auto_fix,
        max_retries=req.max_retries,
        params=req.params,
    )

    # 优先使用 Celery 任务队列，失败时降级到 BackgroundTasks
    use_celery = False
    celery_task_id = None
    try:
        task_result = run_automation_script_task.delay(**task_kwargs)
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"脚本 #{script_id} 已提交 Celery 任务: task_id={celery_task_id}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")
        background_tasks.add_task(_run_script_background, **task_kwargs)

    return {
        "run_id": run.id,
        "status": "running",
        "message": "脚本已提交执行队列，请通过执行记录接口查询状态",
        "auto_fix": req.auto_fix,
        "max_retries": req.max_retries,
        "executor": "celery" if use_celery else "background",
        "celery_task_id": celery_task_id,
    }


@router.get("/{script_id}/runs")
def get_script_runs(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取脚本历史执行记录"""
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    # 通过 source_run_id 关联的执行记录，以及 case_id 关联的执行记录
    runs = db.query(TestRun).filter(
        TestRun.project_id == project_id,
    ).order_by(TestRun.created_at.desc()).limit(50).all()

    # 过滤出与该脚本相关的执行（通过 execution_log 中的 script_id 或脚本名称匹配）
    result = []
    for r in runs:
        log = r.execution_log or ""
        matched = False
        # 优先通过 JSON 中的 script_id 匹配
        if log.startswith("["):
            try:
                log_list = json.loads(log)
                for entry in log_list:
                    if entry.get("script_id") == script_id:
                        matched = True
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        # 兑容旧数据：通过脚本名称匹配
        if not matched and script.name in log:
            matched = True
        # 通过 source_run_id 匹配
        if not matched and script.source_run_id and r.id == script.source_run_id:
            matched = True

        if matched:
            result.append({
                "id": r.id,
                "status": r.status,
                "duration": r.duration,
                "error_message": r.error_message,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "created_at": r.created_at,
            })
    return result[:20]

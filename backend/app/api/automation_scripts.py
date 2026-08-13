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


@router.post("/{script_id}/run")
async def run_script(
    project_id: int,
    script_id: int,
    req: ScriptRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    运行单个脚本
    使用 asyncio 动态执行脚本内容
    """
    _check_project_access(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    # 参数替换
    script_content = script.script_content
    if req.params:
        for key, value in req.params.items():
            script_content = script_content.replace(f"{{{{{key}}}}}", str(value))

    # 创建执行记录
    run = TestRun(
        project_id=project_id,
        case_id=script.case_id,
        status="running",
        execution_log=json.dumps([{"action": "script_run", "detail": f"执行脚本: {script.name}"}], ensure_ascii=False),
        executed_by=current_user.id,
        started_at=china_now_naive(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    import asyncio
    import traceback
    from datetime import datetime

    start_time = time.time()
    start_datetime = china_now_naive()
    error_msg = ""
    status_result = "passed"
    exec_log = [
        {"action": "script_run", "detail": f"执行脚本: {script.name}", "timestamp": start_time, "status": "running", "script_id": script_id}
    ]

    try:
        # 动态执行脚本
        local_vars = {}
        exec(compile(script_content, f"script_{script_id}.py", "exec"), local_vars)

        if "run_test" in local_vars and callable(local_vars["run_test"]):
            await local_vars["run_test"]()
        else:
            raise RuntimeError("脚本中未找到 run_test 函数")

        duration = time.time() - start_time
        exec_log.append({
            "action": "result", "detail": f"执行成功，耗时: {duration:.2f}s",
            "timestamp": time.time(), "status": "passed", "duration": round(duration, 3)
        })

    except Exception as e:
        error_msg = str(e)
        status_result = "failed"
        duration = time.time() - start_time
        traceback.print_exc()
        exec_log.append({
            "action": "result", "detail": f"执行失败，耗时: {duration:.2f}s, 错误: {error_msg}",
            "timestamp": time.time(), "status": "failed", "duration": round(duration, 3),
            "error": error_msg
        })

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

    return {
        "run_id": run.id,
        "status": status_result,
        "duration": round(duration, 2),
        "error": error_msg,
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

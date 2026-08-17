"""
自动化脚本管理 API
"""
import json
import logging
import time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.automation_script import AutomationScript
from app.models.automation_suite import AutomationSuite, AutomationSuiteStep
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.agent_task import AgentTask
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

@router.post("/search", response_model=List[AutomationScriptResponse])
def list_scripts(
    project_id: int,
    status: Optional[str] = Body(None),
    case_id: Optional[int] = Body(None),
    keyword: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取脚本列表"""
    get_project(project_id, db, current_user)
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
    get_project(project_id, db, current_user)
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建脚本（支持AI异步生成）"""
    get_project(project_id, db, current_user)

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
    db.flush()

    # 创建 AgentTask 记录（AI生成脚本）
    agent_task_id = None
    if is_ai:
        agent_task = AgentTask(
            project_id=project_id,
            agent_type="script_generator",
            status="pending",
            input_params={
                "script_id": script.id,
                "description": data.description,
                "target_url": data.target_url,
                "need_ai_name": need_ai_name,
                "prompt_id": data.prompt_id,
            },
            llm_config_id=data.llm_config_id,
            created_by=current_user.id,
        )
        db.add(agent_task)
        db.flush()
        agent_task_id = agent_task.id

    log_audit(
        db, action="create", resource_type="script",
        resource_id=script.id, resource_name=script.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": script.name, "ai_generate": is_ai},
    )
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
            agent_task_id=agent_task_id,
            prompt_id=data.prompt_id,
        )

    return script

def _generate_script_background(
    script_id: int,
    description: str,
    target_url: str,
    script_name: str,
    llm_config_id: Optional[int] = None,
    need_ai_name: bool = False,
    agent_task_id: Optional[int] = None,
    prompt_id: Optional[int] = None,
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
        if agent_task_id:
            agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
            if agent_task:
                agent_task.status = "running"
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

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"使用自定义 Prompt: {prompt_obj.name}")

        # 调用AI生成脚本内容
        generated_content = asyncio.run(
            ScriptGenerator.generate_with_ai(
                description=description,
                target_url=target_url,
                script_name=final_name,
                llm_config_id=llm_config_id,
                db_session=db,
                system_prompt=system_prompt,
            )
        )

        script.script_content = generated_content
        script.status = "active"
        script.version = (script.version or 1) + 1
        script.updated_at = china_now_naive()

        # 更新 AgentTask
        if agent_task_id:
            agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
            if agent_task:
                agent_task.status = "success"
                agent_task.output_result = {"script_id": script_id, "script_name": final_name, "content_length": len(generated_content)}
                agent_task.completed_at = china_now_naive()

        db.commit()
        logger.info(f"AI脚本生成完成: script_id={script_id}")

    except Exception as e:
        logger.error(f"AI脚本生成失败: script_id={script_id}, error={e}", exc_info=True)
        try:
            script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
            if script:
                script.status = "failed"
                script.description = f"{script.description}\n\n[AI生成失败: {str(e)[:200]}]"
            if agent_task_id:
                agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
                if agent_task:
                    agent_task.status = "failed"
                    agent_task.error_message = str(e)
                    agent_task.completed_at = china_now_naive()
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新脚本"""
    get_project(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    old_data = {"name": script.name, "status": script.status, "version": script.version}
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(script, key, value)
    script.version = (script.version or 1) + 1
    script.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="script",
        resource_id=script.id, resource_name=script.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": {k: v for k, v in update_data.items() if k != "script_content"}, "new_version": script.version},
    )
    db.commit()
    db.refresh(script)
    return script

@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_script(
    project_id: int,
    script_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除脚本"""
    get_project(project_id, db, current_user)
    script = db.query(AutomationScript).filter(
        AutomationScript.id == script_id,
        AutomationScript.project_id == project_id,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    script_name = script.name
    script.soft_delete()
    log_audit(
        db, action="delete", resource_type="script",
        resource_id=script_id, resource_name=script_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

@router.post("/{script_id}/duplicate", response_model=AutomationScriptResponse)
def duplicate_script(
    project_id: int,
    script_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """复制脚本"""
    get_project(project_id, db, current_user)
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
    db.flush()
    log_audit(
        db, action="create", resource_type="script",
        resource_id=new_script.id, resource_name=new_script.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "duplicated_from": script_id, "name": new_script.name},
    )
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
    get_project(project_id, db, current_user)
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
    headless: bool = True,
):
    """
    后台执行脚本，支持AI自动修复重试
    委托给 script_runner 统一服务执行
    """
    from app.database import SessionLocal
    from app.services.script_runner import execute_script_with_ai_fix

    db = SessionLocal()
    try:
        await execute_script_with_ai_fix(
            db=db,
            run_id=run_id,
            script_id=script_id,
            project_id=project_id,
            script_content=script_content,
            script_name=script_name,
            target_url=target_url,
            auto_fix=auto_fix,
            max_retries=max_retries,
            params=params,
            headless=headless,
            executor="background",
        )
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
    request: Request,
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
    get_project(project_id, db, current_user)
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
    db.flush()
    log_audit(
        db, action="execute", resource_type="script",
        resource_id=script.id, resource_name=script.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "run_id": run.id, "auto_fix": req.auto_fix, "max_retries": req.max_retries},
    )
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
        headless=req.headless,
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

@router.get("/{script_id}/suites")
def get_script_suites(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取引用该脚本的所有编排套件"""
    get_project(project_id, db, current_user)
    # 查找所有引用该脚本的步骤
    steps = db.query(AutomationSuiteStep).filter(
        AutomationSuiteStep.script_id == script_id,
    ).all()
    suite_ids = list(set(s.suite_id for s in steps))
    if not suite_ids:
        return []
    suites = db.query(AutomationSuite).filter(
        AutomationSuite.id.in_(suite_ids),
        AutomationSuite.project_id == project_id,
    ).all()
    result = []
    for suite in suites:
        suite_steps = [s for s in steps if s.suite_id == suite.id]
        result.append({
            "suite_id": suite.id,
            "suite_name": suite.name,
            "status": suite.status,
            "step_names": [s.step_name for s in suite_steps],
        })
    return result

@router.get("/{script_id}/runs")
def get_script_runs(
    project_id: int,
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取脚本历史执行记录"""
    get_project(project_id, db, current_user)
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

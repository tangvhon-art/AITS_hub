"""
报告生成相关的 Celery 任务
在独立 worker 进程中执行报告生成（统计数据 + AI增强）
直接使用 call_with_fallback 调用 LLM，不经过 Agent 链路
"""
import logging
import re
from typing import Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.report import TestReport
from app.models.agent_task import AgentTask
from app.agents.report_generator import ReportGeneratorAgent, REPORT_PROMPT
from app.core.timezone import china_now_naive
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_test_report", max_retries=0, queue="ai")
def generate_test_report_task(
    self,
    report_id: int,
    project_id: int,
    report_type: str,
    version_id: int,
    title: str,
    llm_config_id: Optional[int] = None,
    agent_task_id: Optional[int] = None,
):
    """Celery 任务：生成测试报告 — 直接使用 call_with_fallback"""
    db = SessionLocal()
    try:
        report = db.query(TestReport).filter(TestReport.id == report_id).first()
        if not report:
            logger.error(f"报告记录不存在: report_id={report_id}")
            return {"status": "failed", "error": "报告记录不存在"}

        logger.info(f"[report] 开始生成测试报告: report_id={report_id}, title={title}")

        # 获取自定义 Prompt
        system_prompt = ""
        if agent_task_id:
            agent_task_record = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
            if agent_task_record:
                prompt_id = (agent_task_record.input_params or {}).get("prompt_id")
                if prompt_id:
                    from app.models.prompt import Prompt
                    prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
                    if prompt_obj:
                        system_prompt = prompt_obj.system_prompt or ""
                        logger.info(f"[report] 使用自定义 Prompt: {prompt_obj.name}")

        if not system_prompt:
            system_prompt = REPORT_PROMPT

        # 用 ReportGeneratorAgent 收集统计数据（只用统计逻辑，不用 _call_llm）
        agent = ReportGeneratorAgent(db, llm_config_id=llm_config_id, project_id=project_id)
        stats = agent._collect_stats(project_id, version_id=version_id)
        stats_text = agent._format_stats_text(stats, "", report_type)

        # 直接调用 LLM — 使用 call_with_fallback（同用例生成/评审路径）
        from langchain_core.messages import SystemMessage, HumanMessage
        from app.agents.llm_factory import llm_factory

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=stats_text),
        ]

        logger.info(f"[report] 开始调用 LLM, stats_keys={len(stats)}")

        import time
        start = time.time()
        response, token_usage, used_config_id = llm_factory.call_with_fallback(
            db,
            messages,
            preferred_config_id=llm_config_id,
            max_tokens=8192,
            temperature=0.3,
        )
        elapsed = time.time() - start

        raw_content = response.content if hasattr(response, "content") else str(response)
        logger.info(
            f"[report] LLM 调用完成: elapsed={elapsed:.1f}s, "
            f"content_len={len(raw_content)}, tokens={token_usage}, config_id={used_config_id}"
        )

        # 内容清洗
        content = re.sub(r'["\u201c\u201d]{5,}', '', raw_content)
        content = re.sub(r'[()]{5,}', '', content)
        content = re.sub(r',{3,}', '，', content)
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        if len(content) > 8000:
            content = content[:8000] + '\n\n...（内容已截断）'

        # 提取报告内容并更新
        from app.services.content_extractor import ContentExtractor
        from app.services.ai_creation_service import AICreationService

        report_content = ContentExtractor.extract_report(content)
        AICreationService.update_report(
            db,
            report,
            content=report_content,
            summary=stats,
            stats={
                "total_cases": stats.get("total_cases", 0),
                "passed_cases": stats.get("passed_cases", 0),
                "failed_cases": stats.get("failed_cases", 0),
                "pass_rate": stats.get("pass_rate", 0.0),
                "total_defects": stats.get("total_defects", 0),
                "open_defects": stats.get("open_defects", 0),
                "total_runs": stats.get("total_runs", 0),
                "avg_duration": stats.get("avg_duration", 0.0),
            },
        )

        # 更新 Agent 任务
        if agent_task_id:
            agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
            if agent_task:
                agent_task.status = "success"
                agent_task.output_result = {
                    "report_id": report.id,
                    "total_cases": report.total_cases,
                    "pass_rate": report.pass_rate,
                }
                agent_task.token_usage = token_usage
                agent_task.llm_config_id = used_config_id
                agent_task.completed_at = china_now_naive()

        db.commit()
        logger.info(f"[report] 测试报告生成成功: report_id={report_id}, pass_rate={report.pass_rate}%")

        # 发送AI报告生成完成通知
        try:
            version_name = "-"
            if version_id:
                from app.models.project_version import ProjectVersion
                ver = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
                if ver:
                    version_name = ver.name
            type_map = {"daily": "日报", "weekly": "周报", "monthly": "月报", "version": "版本报告"}
            period = type_map.get(report_type, report_type)
            report_triggered_by = None
            if agent_task_id:
                at = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
                if at:
                    report_triggered_by = at.created_by
            notify_event(
                project_id,
                "ai.report.generated",
                {
                    "report_id": report.id,
                    "report_name": title,
                    "version_name": version_name,
                    "period": period,
                    "pass_rate": report.pass_rate or 0,
                    "defect_count": report.total_defects or 0,
                },
                triggered_by=report_triggered_by,
            )
        except Exception as notify_e:
            logger.warning(f"[report] 发送报告生成通知失败: {notify_e}")

        return {
            "status": "success",
            "report_id": report_id,
            "total_cases": report.total_cases,
            "pass_rate": report.pass_rate,
        }

    except Exception as e:
        logger.error(f"[report] 生成测试报告异常: report_id={report_id}, error={e}", exc_info=True)
        try:
            report = db.query(TestReport).filter(TestReport.id == report_id).first()
            if report:
                report.status = "failed"
                report.content = f"报告生成失败: {str(e)}"
                report.updated_at = china_now_naive()
            if agent_task_id:
                agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
                if agent_task:
                    agent_task.status = "failed"
                    agent_task.error_message = str(e)
                    agent_task.completed_at = china_now_naive()
                    notify_ai_task_failed(
                        project_id,
                        task_type="测试报告生成",
                        error=str(e),
                        related_object=title,
                        triggered_by=agent_task.created_by,
                    )
            db.commit()
        except Exception:
            pass
        return {"status": "failed", "report_id": report_id, "error": str(e)}
    finally:
        db.close()

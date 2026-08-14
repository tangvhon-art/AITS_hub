"""
报告生成相关的 Celery 任务
在独立 worker 进程中执行报告生成（统计数据 + AI增强）
"""
import logging
from typing import Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.report import TestReport
from app.models.agent_task import AgentTask
from app.agents.report_generator import ReportGeneratorAgent
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_test_report", max_retries=0)
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
    """
    Celery 任务：生成测试报告

    Args:
        report_id: 报告记录ID
        project_id: 项目ID
        report_type: 报告类型
        version_id: 版本ID
        title: 报告标题
        llm_config_id: LLM配置ID（可选）
        agent_task_id: 关联的 AgentTask ID（可选）
    """
    db = SessionLocal()
    try:
        report = db.query(TestReport).filter(TestReport.id == report_id).first()
        if not report:
            logger.error(f"报告记录不存在: report_id={report_id}")
            return {"status": "failed", "error": "报告记录不存在"}

        logger.info(f"开始生成测试报告: report_id={report_id}, title={title}")

        # 调用报告生成 Agent
        agent = ReportGeneratorAgent(db, llm_config_id=llm_config_id)
        result = agent.generate(
            project_id=project_id,
            report_type=report_type,
            title=title,
            version_id=version_id,
        )

        # 更新报告
        report.content = result.get("content", "")
        report.summary = result.get("summary", {})
        report.total_cases = result.get("total_cases", 0)
        report.passed_cases = result.get("passed_cases", 0)
        report.failed_cases = result.get("failed_cases", 0)
        report.pass_rate = result.get("pass_rate", 0.0)
        report.total_defects = result.get("total_defects", 0)
        report.open_defects = result.get("open_defects", 0)
        report.total_runs = result.get("total_runs", 0)
        report.avg_duration = result.get("avg_duration", 0.0)
        report.status = "completed"
        report.updated_at = china_now_naive()

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
                agent_task.token_usage = result.get("token_usage", {})
                agent_task.completed_at = china_now_naive()

        db.commit()
        logger.info(f"测试报告生成成功: report_id={report_id}, pass_rate={report.pass_rate}%")

        return {
            "status": "success",
            "report_id": report_id,
            "total_cases": report.total_cases,
            "pass_rate": report.pass_rate,
        }

    except Exception as e:
        logger.error(f"生成测试报告异常: report_id={report_id}, error={e}", exc_info=True)
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
            db.commit()
        except Exception:
            pass
        return {"status": "failed", "report_id": report_id, "error": str(e)}
    finally:
        db.close()

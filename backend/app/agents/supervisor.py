"""
Supervisor 监督者编排引擎

使用 LangGraph 状态机编排多 Agent 协同流程：
需求 → 用例生成 → 用例评审 → (人工确认) → 执行 → 缺陷分析 → 报告生成 → 通知
"""
import json
import logging
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


# 定义 Supervisor 状态
class SupervisorState(TypedDict, total=False):
    """Supervisor 状态"""
    project_id: int
    requirement_id: Optional[int]
    requirement_content: str
    requirement_title: str

    # 用例生成
    cases: List[Dict[str, Any]]
    generate_count: int

    # 用例评审
    review_result: Dict[str, Any]
    review_passed: bool

    # 执行
    execution_results: List[Dict[str, Any]]
    target_url: str

    # 缺陷
    defects: List[Dict[str, Any]]

    # 报告
    report: Dict[str, Any]

    # 通知
    notification_result: Dict[str, Any]

    # 流程控制
    current_node: str
    errors: List[str]
    created_by: Optional[int]
    llm_config_id: Optional[int]


class SupervisorEngine:
    """Supervisor 编排引擎"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def run_full_pipeline(
        self,
        project_id: int,
        requirement_content: str,
        requirement_title: str = "",
        generate_count: int = 10,
        target_url: str = "",
        llm_config_id: Optional[int] = None,
        created_by: Optional[int] = None,
        auto_execute: bool = False,
        notification_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        运行完整流水线（同步模式，用于演示和小规模任务）

        Args:
            project_id: 项目ID
            requirement_content: 需求内容
            requirement_title: 需求标题
            generate_count: 生成用例数量
            target_url: 执行目标URL
            llm_config_id: 模型配置ID
            created_by: 创建人
            auto_execute: 是否自动执行（默认只生成+评审，执行需要人工触发）
            notification_config: 通知配置

        Returns:
            流水线结果
        """
        from app.agents.case_generator import CaseGeneratorAgent
        from app.agents.case_reviewer import CaseReviewerAgent
        from app.agents.defect_analyzer import DefectAnalyzerAgent
        from app.agents.report_generator import ReportGeneratorAgent
        from app.agents.notification_agent import NotificationAgent
        from app.models.agent_task import AgentTask
        from app.models.test_case import TestCase
        from app.models.defect import Defect
        from app.models.report import TestReport
        from app.services.content_extractor import ContentExtractor
        from app.services.ai_creation_service import AICreationService

        results = {
            "project_id": project_id,
            "started_at": china_now_naive().isoformat(),
            "steps": [],
            "errors": [],
        }

        # Step 1: 用例生成
        logger.info("Supervisor: 开始用例生成")
        try:
            gen_agent = CaseGeneratorAgent(self.db, llm_config_id=llm_config_id)
            gen_result = gen_agent.generate(requirement_content, count=generate_count)
            cases = ContentExtractor.extract_test_cases(gen_result["raw_content"])
            created_cases = AICreationService.create_test_cases(
                self.db, project_id=project_id, cases=cases, created_by=created_by,
            )
            saved_cases = [{"id": c.id, "title": c.title, "module": c.module,
                            "priority": c.priority, "case_type": c.case_type,
                            "preconditions": c.preconditions, "steps": c.steps,
                            "expected_result": c.expected_result} for c in created_cases]

            results["cases"] = saved_cases
            results["steps"].append({
                "step": "case_generation",
                "status": "success",
                "count": len(saved_cases),
                "token_usage": gen_result.get("token_usage", {}),
            })
            logger.info(f"Supervisor: 用例生成完成，共 {len(saved_cases)} 条")

        except Exception as e:
            logger.error(f"Supervisor: 用例生成失败: {e}")
            results["errors"].append(f"用例生成失败: {str(e)}")
            results["steps"].append({"step": "case_generation", "status": "failed", "error": str(e)})
            return results

        # Step 2: 用例评审
        logger.info("Supervisor: 开始用例评审")
        try:
            reviewer = CaseReviewerAgent(self.db, llm_config_id=llm_config_id)
            agent_result = reviewer.review(cases, requirement=requirement_content)
            review_result = ContentExtractor.extract_review(agent_result["raw_content"])
            results["review_result"] = review_result
            results["steps"].append({
                "step": "case_review",
                "status": "success",
                "score": review_result.get("score"),
                "passed": review_result.get("passed"),
            })
            logger.info(f"Supervisor: 用例评审完成，评分 {review_result.get('score')}")

        except Exception as e:
            logger.error(f"Supervisor: 用例评审失败: {e}")
            results["errors"].append(f"用例评审失败: {str(e)}")
            results["steps"].append({"step": "case_review", "status": "failed", "error": str(e)})

        # Step 3: 执行（可选）
        if auto_execute and target_url:
            logger.info("Supervisor: 开始自动执行")
            execution_results = []
            for case_data in saved_cases[:3]:  # 最多执行3条演示
                try:
                    from app.agents.execution_agent import ExecutionAgent
                    from app.models.test_run import TestRun
                    from app.core.async_runner import run_async

                    exec_agent = ExecutionAgent(self.db, project_id=project_id, llm_config_id=llm_config_id)
                    instruction = self._case_to_instruction(case_data)

                    # 桥接 sync → async：消费 ExecutionAgent.execute() 异步生成器
                    # （统一异步桥接 run_async：自动规避 eventlet 协程池下
                    #   同一 OS 线程多个 running event loop 冲突）
                    async def _run_execution():
                        step_logs = []
                        final_status = "passed"
                        error_message = ""
                        async for step in exec_agent.execute(instruction, target_url=target_url, headless=True):
                            step_logs.append(step)
                            if step.get("type") == "error":
                                final_status = "failed"
                                error_message = step.get("error", "")
                            elif step.get("type") == "complete":
                                final_status = step.get("status", "passed")
                        return final_status, error_message, step_logs

                    final_status, error_msg, step_logs = run_async(_run_execution)

                    # 创建 TestRun 记录
                    run = TestRun(
                        project_id=project_id,
                        case_id=case_data.get("id"),
                        status=final_status,
                        duration=sum(s.get("duration", 0) for s in step_logs if isinstance(s.get("duration"), (int, float))),
                        execution_log=json.dumps(step_logs, ensure_ascii=False, default=str),
                        error_message=error_msg,
                        target_url=target_url,
                        created_by=created_by,
                    )
                    self.db.add(run)
                    self.db.flush()

                    exec_result = {
                        "case_id": case_data.get("id"),
                        "run_id": run.id,
                        "status": final_status,
                        "error_message": error_msg,
                        "execution_log": json.dumps(step_logs, ensure_ascii=False, default=str),
                        "step_count": len(step_logs),
                    }
                    execution_results.append(exec_result)
                    logger.info(f"Supervisor: 用例 {case_data.get('id')} 执行完成，状态: {final_status}")

                except Exception as e:
                    logger.error(f"Supervisor: 用例执行失败: {e}")
                    execution_results.append({
                        "case_id": case_data.get("id"),
                        "status": "error",
                        "error": str(e),
                    })

            results["execution_results"] = execution_results
            passed_count = sum(1 for r in execution_results if r.get("status") == "passed")
            results["steps"].append({
                "step": "execution",
                "status": "success" if passed_count == len(execution_results) else "partial",
                "count": len(execution_results),
                "passed": passed_count,
                "failed": len(execution_results) - passed_count,
            })

        # Step 4: 缺陷分析（如果有失败执行）
        failed_runs = [r for r in results.get("execution_results", []) if r.get("status") == "failed"]
        if failed_runs:
            logger.info("Supervisor: 开始缺陷分析")
            defects = []
            for run in failed_runs:
                try:
                    defect_agent = DefectAnalyzerAgent(self.db, llm_config_id=llm_config_id)
                    agent_result = defect_agent.analyze(
                        execution_log=run.get("execution_log", ""),
                        error_message=run.get("error_message", ""),
                        test_case=run.get("case_data"),
                    )
                    defect_data = ContentExtractor.extract_defect(agent_result["raw_content"])
                    defect = AICreationService.create_defect(
                        self.db,
                        project_id=project_id,
                        defect_data=defect_data,
                        run_id=run.get("run_id"),
                        case_id=run.get("case_id"),
                        created_by=created_by,
                    )
                    defects.append({"id": defect.id, "title": defect.title})
                except Exception as e:
                    logger.error(f"缺陷分析失败: {e}")

            results["defects"] = defects
            results["steps"].append({"step": "defect_analysis", "status": "success", "count": len(defects)})

        # Step 5: 报告生成
        logger.info("Supervisor: 开始报告生成")
        try:
            report_agent = ReportGeneratorAgent(self.db, llm_config_id=llm_config_id)
            report_result = report_agent.generate(
                project_id=project_id,
                report_type="full",
                title=f"测试报告 - {requirement_title or china_now_naive().strftime('%Y-%m-%d')}",
            )
            report_content = ContentExtractor.extract_report(report_result["raw_content"])
            report = TestReport(
                project_id=project_id,
                title=report_result.get("title", "测试报告"),
                report_type="full",
                status="completed",
                content=report_content,
                summary=report_result.get("summary", {}),
                total_cases=report_result.get("total_cases", 0),
                passed_cases=report_result.get("passed_cases", 0),
                failed_cases=report_result.get("failed_cases", 0),
                pass_rate=report_result.get("pass_rate", 0.0),
                total_defects=report_result.get("total_defects", 0),
                open_defects=report_result.get("open_defects", 0),
                total_runs=report_result.get("total_runs", 0),
                avg_duration=report_result.get("avg_duration", 0.0),
                created_by=created_by,
            )
            self.db.add(report)
            self.db.flush()
            results["report"] = {"id": report.id, "title": report.title}
            results["steps"].append({"step": "report_generation", "status": "success", "report_id": report.id})

        except Exception as e:
            logger.error(f"Supervisor: 报告生成失败: {e}")
            results["errors"].append(f"报告生成失败: {str(e)}")
            results["steps"].append({"step": "report_generation", "status": "failed", "error": str(e)})

        # Step 6: 通知
        if notification_config:
            logger.info("Supervisor: 发送通知")
            try:
                notif_agent = NotificationAgent(self.db)
                notif_result = notif_agent.send(
                    title=f"测试流程完成 - {requirement_title or '未命名'}",
                    content=self._build_notification_content(results),
                    channels=notification_config.get("channels", ["email"]),
                    email_to=notification_config.get("email_to", []),
                    feishu_webhook=notification_config.get("feishu_webhook", ""),
                )
                results["notification_result"] = notif_result
                results["steps"].append({"step": "notification", "status": "success"})
            except Exception as e:
                logger.error(f"Supervisor: 通知发送失败: {e}")
                results["errors"].append(f"通知发送失败: {str(e)}")

        self.db.commit()
        results["completed_at"] = china_now_naive().isoformat()
        results["status"] = "completed" if not results["errors"] else "partial"
        return results

    def _case_to_instruction(self, case: Dict[str, Any]) -> str:
        """将用例转换为自然语言指令"""
        steps = case.get("steps", [])
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except (json.JSONDecodeError, TypeError):
                steps = [steps]

        steps_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(steps)]) if steps else ""
        return f"执行测试用例：{case.get('title', '')}\n前置条件：{case.get('preconditions', '')}\n步骤：\n{steps_text}\n预期结果：{case.get('expected_result', '')}"

    def _build_notification_content(self, results: Dict[str, Any]) -> str:
        """构建通知内容"""
        lines = [
            "## 测试流程完成通知",
            f"- 项目ID: {results.get('project_id')}",
            f"- 状态: {results.get('status')}",
        ]
        for step in results.get("steps", []):
            lines.append(f"- {step.get('step')}: {step.get('status')}")
        if results.get("errors"):
            lines.append(f"\n**错误:** {'; '.join(results['errors'])}")
        return "\n".join(lines)

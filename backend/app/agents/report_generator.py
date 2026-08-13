"""
报告生成 Agent

聚合用例/执行/缺陷数据，生成测试报告。
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import func
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.defect import Defect

logger = logging.getLogger(__name__)


REPORT_PROMPT = """你是一位资深测试报告撰写专家。

请根据以下测试数据，生成一份专业的测试报告（Markdown格式），包含：
1. 测试概览（通过率、用例数、缺陷数等关键指标）
2. 测试执行情况分析
3. 缺陷分析与分布
4. 风险评估
5. 测试结论与建议

要求：
- 数据准确，基于提供的统计数据
- 分析深入，不仅是数据罗列
- 语言专业、简洁
- Markdown 格式，包含适当的标题和列表
"""


class ReportGeneratorAgent(BaseAgent):
    """报告生成 Agent"""

    agent_type = "report_generator"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行报告生成"""
        return self.generate(
            project_id=kwargs.get("project_id", 0),
            report_type=kwargs.get("report_type", "summary"),
            title=kwargs.get("title", ""),
        )

    def generate(
        self,
        project_id: int,
        report_type: str = "summary",
        title: str = "",
    ) -> Dict[str, Any]:
        """
        生成测试报告

        Args:
            project_id: 项目ID
            report_type: 报告类型
            title: 报告标题

        Returns:
            报告内容
        """
        import time
        self.start_time = time.time()
        self._log_step("report_start", {"project_id": project_id}, "running")

        # 收集统计数据
        stats = self._collect_stats(project_id)
        self._log_step("stats_collected", stats, "success")

        # 生成报告内容
        messages = [
            SystemMessage(content=REPORT_PROMPT),
            HumanMessage(content=f"项目ID: {project_id}\n报告类型: {report_type}\n\n统计数据:\n{json.dumps(stats, ensure_ascii=False, indent=2)}"),
        ]

        try:
            response = self._call_llm(messages)
            self._log_step("llm_call", {}, "success")

            report_content = response.content
            report_title = title or f"测试报告 - {china_now_naive().strftime('%Y-%m-%d')}"

            result = {
                "title": report_title,
                "content": report_content,
                "summary": stats,
                "report_type": report_type,
                "total_cases": stats.get("total_cases", 0),
                "passed_cases": stats.get("passed_cases", 0),
                "failed_cases": stats.get("failed_cases", 0),
                "pass_rate": stats.get("pass_rate", 0.0),
                "total_defects": stats.get("total_defects", 0),
                "open_defects": stats.get("open_defects", 0),
                "total_runs": stats.get("total_runs", 0),
                "avg_duration": stats.get("avg_duration", 0.0),
                "token_usage": self.get_token_usage(),
                "llm_config_id": self.llm_config_id,
            }

            self._log_step("report_complete", {"title": report_title}, "success")
            return result

        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            self._log_step("report_error", {"error": str(e)}, "failed")
            # 降级返回基础报告
            basic_content = self._generate_basic_report(stats)
            return {
                "title": title or f"测试报告 - {china_now_naive().strftime('%Y-%m-%d')}",
                "content": basic_content,
                "summary": stats,
                "report_type": report_type,
                "total_cases": stats.get("total_cases", 0),
                "passed_cases": stats.get("passed_cases", 0),
                "failed_cases": stats.get("failed_cases", 0),
                "pass_rate": stats.get("pass_rate", 0.0),
                "total_defects": stats.get("total_defects", 0),
                "open_defects": stats.get("open_defects", 0),
                "total_runs": stats.get("total_runs", 0),
                "avg_duration": stats.get("avg_duration", 0.0),
                "error": str(e),
                "token_usage": self.get_token_usage(),
            }

    def _collect_stats(self, project_id: int) -> Dict[str, Any]:
        """收集项目统计数据"""
        # 用例统计
        total_cases = self.db.query(func.count(TestCase.id)).filter(
            TestCase.project_id == project_id
        ).scalar() or 0

        # 执行统计
        runs = self.db.query(TestRun).filter(TestRun.project_id == project_id).all()
        total_runs = len(runs)
        passed_runs = sum(1 for r in runs if r.status == "passed")
        failed_runs = sum(1 for r in runs if r.status == "failed")
        durations = [r.duration for r in runs if r.duration and r.duration > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0.0

        # 缺陷统计
        total_defects = self.db.query(func.count(Defect.id)).filter(
            Defect.project_id == project_id
        ).scalar() or 0
        open_defects = self.db.query(func.count(Defect.id)).filter(
            Defect.project_id == project_id,
            Defect.status.in_(["open", "confirmed", "reopened"]),
        ).scalar() or 0

        # 缺陷按严重程度分布
        severity_dist = {}
        severity_counts = self.db.query(
            Defect.severity, func.count(Defect.id)
        ).filter(
            Defect.project_id == project_id
        ).group_by(Defect.severity).all()
        for sev, count in severity_counts:
            severity_dist[sev] = count

        # 缺陷按根因分类分布
        category_dist = {}
        category_counts = self.db.query(
            Defect.root_cause_category, func.count(Defect.id)
        ).filter(
            Defect.project_id == project_id,
            Defect.root_cause_category != "",
        ).group_by(Defect.root_cause_category).all()
        for cat, count in category_counts:
            category_dist[cat] = count

        return {
            "total_cases": total_cases,
            "total_runs": total_runs,
            "passed_cases": passed_runs,
            "failed_cases": failed_runs,
            "pass_rate": round(pass_rate, 2),
            "total_defects": total_defects,
            "open_defects": open_defects,
            "avg_duration": round(avg_duration, 2),
            "severity_distribution": severity_dist,
            "category_distribution": category_dist,
        }

    def _generate_basic_report(self, stats: Dict[str, Any]) -> str:
        """生成基础报告（降级用）"""
        return f"""# 测试报告

## 测试概览
- 用例总数：{stats.get('total_cases', 0)}
- 执行次数：{stats.get('total_runs', 0)}
- 通过：{stats.get('passed_cases', 0)}
- 失败：{stats.get('failed_cases', 0)}
- 通过率：{stats.get('pass_rate', 0)}%
- 缺陷总数：{stats.get('total_defects', 0)}
- 未解决缺陷：{stats.get('open_defects', 0)}

## 说明
本报告为自动生成的基础版本，详细分析请使用 AI 生成模式。
"""

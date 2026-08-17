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

from app.core.timezone import china_now_naive
from app.agents.base_agent import BaseAgent
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.defect import Defect
from app.models.test_plan import TestPlan, TestPlanItem, TestPlanExecution
from app.models.requirement import TestRequirement
from app.models.project_version import ProjectVersion
from app.models.api_test import ApiExecution

logger = logging.getLogger(__name__)


REPORT_PROMPT = """你是一位资深测试报告撰写专家，拥有丰富的软件质量保障和测试分析经验。你的任务是根据提供的测试统计数据，生成一份专业、深入、可执行的测试报告。

## 输出格式

输出一份结构化的 Markdown 格式测试报告。不要输出 JSON，直接输出 Markdown 文本。

## 报告结构（使用 Markdown 二级标题 ## 分隔）

### 1. 测试概览
以表格或列表形式呈现关键指标：
- 用例总数、执行次数、通过数、失败数、通过率
- UI 自动化执行与接口自动化执行分别统计
- 缺陷总数、未解决缺陷数
- 测试计划执行情况（如有关联版本）
- 平均执行时长

### 2. 测试执行情况分析
- 对比 UI 自动化与接口自动化的执行情况
- 分析通过率是否达标（通常 ≥95% 为合格）
- 识别失败率较高的模块或接口
- 执行效率分析（平均时长是否在合理范围）

### 3. 缺陷分析与分布
- 按严重程度（blocker/critical/major/minor/trivial）分布分析
- 按根因分类（frontend/backend/data/environment/requirement/other）分布分析
- 识别缺陷集中的模块或领域
- 评估未解决缺陷的风险等级

### 4. 风险评估
- 基于通过率和缺陷分布，评估当前版本质量风险
- 识别高风险区域（失败率高、blocker/critical 缺陷未解决）
- 评估是否具备发布条件

### 5. 测试结论与建议
- 给出明确的测试结论（通过/有条件通过/不通过）
- 列出具体的改进建议（按优先级排序）
- 后续测试重点方向

## 生成原则
- 所有数据必须基于提供的统计数据，禁止编造数据
- 分析要深入，不仅是数据罗列，要给出原因分析和改进方向
- 语言专业、简洁、客观
- 使用 Markdown 格式，善用表格、列表、加粗等排版
- 如果统计数据中某项为 0，如实说明，不要省略对应章节
- 所有内容使用中文"""


class ReportGeneratorAgent(BaseAgent):
    """报告生成 Agent"""

    agent_type = "report_generator"

    def __init__(self, db_session, llm_config_id: Optional[int] = None, task_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, llm_config_id, task_id, project_id=project_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行报告生成"""
        return self.generate(
            project_id=kwargs.get("project_id", 0),
            report_type=kwargs.get("report_type", "summary"),
            title=kwargs.get("title", ""),
            version_id=kwargs.get("version_id"),
            system_prompt=kwargs.get("system_prompt", ""),
        )

    def generate(
        self,
        project_id: int,
        report_type: str = "summary",
        title: str = "",
        version_id: Optional[int] = None,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        生成测试报告

        Args:
            project_id: 项目ID
            report_type: 报告类型
            title: 报告标题
            version_id: 版本ID（按版本过滤数据）
            system_prompt: 自定义 system 提示词（来自 Prompt 管理）

        Returns:
            报告内容
        """
        import time
        self.start_time = time.time()
        self.project_id = project_id
        self._log_step("report_start", {"project_id": project_id, "version_id": version_id}, "running")

        # 收集统计数据（按版本过滤）
        stats = self._collect_stats(project_id, version_id=version_id)
        self._log_step("stats_collected", stats, "success")

        # 获取版本名称用于提示
        version_name = ""
        if version_id:
            version = self.db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
            version_name = version.name if version else ""

        # P2-9: RAG 知识库增强 - 检索项目质量标准和历史报告
        rag_context = self.build_rag_context(
            f"测试报告 质量分析 {version_name} 通过率 缺陷",
            top_k=3,
        )

        system_content = system_prompt.strip() if system_prompt and system_prompt.strip() else REPORT_PROMPT
        if rag_context:
            system_content += f"\n\n{rag_context}"

        # 生成报告内容
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=(
                f"项目ID: {project_id}\n"
                f"版本: {version_name}\n"
                f"报告类型: {report_type}\n\n"
                f"统计数据:\n{json.dumps(stats, ensure_ascii=False, indent=2)}"
            )),
        ]

        try:
            response = self._call_llm(messages)
            self._log_step("llm_call", {}, "success")

            report_title = title or f"测试报告 - {china_now_naive().strftime('%Y-%m-%d')}"
            logger.info(f"报告生成完成，原始输出长度: {len(response.content)}")

            result = {
                "title": report_title,
                "raw_content": response.content,
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
            raise

    def _collect_stats(self, project_id: int, version_id: Optional[int] = None) -> Dict[str, Any]:
        """收集项目统计数据（可按版本过滤）"""

        # 构建版本关联的用例子查询（统一基于 TestPlanItem）
        if version_id is not None:
            # 版本关联的测试计划 ID 列表
            plan_ids = [
                p[0] for p in self.db.query(TestPlan.id).filter(
                    TestPlan.project_id == project_id,
                    TestPlan.version_id == version_id,
                ).all()
            ]
            # 版本关联的功能用例 ID 列表（通过 TestPlanItem ui_case）
            case_ids = []
            if plan_ids:
                case_ids = [
                    c[0] for c in self.db.query(TestPlanItem.ref_id).filter(
                        TestPlanItem.plan_id.in_(plan_ids),
                        TestPlanItem.item_type == "ui_case",
                        TestPlanItem.is_deleted == False,
                    ).distinct().all()
                ]
            # 版本关联的接口用例 ID 列表（通过 TestPlanItem case）
            api_case_ids = []
            if plan_ids:
                api_case_ids = [
                    c[0] for c in self.db.query(TestPlanItem.ref_id).filter(
                        TestPlanItem.plan_id.in_(plan_ids),
                        TestPlanItem.item_type == "case",
                        TestPlanItem.is_deleted == False,
                    ).distinct().all()
                ]

            # 用例统计：版本关联的用例
            if case_ids:
                total_cases = self.db.query(func.count(TestCase.id)).filter(
                    TestCase.id.in_(case_ids)
                ).scalar() or 0
            else:
                total_cases = 0

            # 执行统计：版本关联用例的执行记录
            if case_ids:
                runs = self.db.query(TestRun).filter(
                    TestRun.project_id == project_id,
                    TestRun.case_id.in_(case_ids),
                ).all()
            else:
                runs = []
        else:
            # 无版本过滤，查询项目全量数据
            total_cases = self.db.query(func.count(TestCase.id)).filter(
                TestCase.project_id == project_id
            ).scalar() or 0
            runs = self.db.query(TestRun).filter(TestRun.project_id == project_id).all()
            api_case_ids = []

        total_runs = len(runs)
        passed_runs = sum(1 for r in runs if r.status == "passed")
        failed_runs = sum(1 for r in runs if r.status == "failed")
        durations = [r.duration for r in runs if r.duration and r.duration > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0.0

        # 接口自动化执行统计
        api_exec_query = self.db.query(ApiExecution).filter(
            ApiExecution.project_id == project_id,
            ApiExecution.is_deleted == False,
        )
        if version_id is not None:
            if api_case_ids:
                api_exec_query = api_exec_query.filter(ApiExecution.case_id.in_(api_case_ids))
            else:
                api_exec_query = api_exec_query.filter(ApiExecution.id == -1)
        api_total_runs = api_exec_query.count()
        api_passed_runs = api_exec_query.filter(ApiExecution.status == "passed").count()
        api_failed_runs = api_exec_query.filter(ApiExecution.status.in_(["failed", "error"])).count()
        api_durations = [r.total_duration for r in api_exec_query.all() if r.total_duration and r.total_duration > 0]
        api_avg_duration = sum(api_durations) / len(api_durations) if api_durations else 0.0

        # 合并 UI + API 执行统计
        total_runs += api_total_runs
        passed_runs += api_passed_runs
        failed_runs += api_failed_runs
        all_durations = durations + api_durations
        avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0.0
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0.0

        # 缺陷统计（按版本过滤）
        defect_query = self.db.query(Defect).filter(Defect.project_id == project_id)
        if version_id is not None:
            defect_query = defect_query.filter(Defect.version_id == version_id)
        defects = defect_query.all()

        total_defects = len(defects)
        open_defects = sum(1 for d in defects if d.status in ["open", "confirmed", "reopened"])

        # 缺陷按严重程度分布
        severity_dist = {}
        for d in defects:
            severity_dist[d.severity] = severity_dist.get(d.severity, 0) + 1

        # 缺陷按根因分类分布
        category_dist = {}
        for d in defects:
            if d.root_cause_category:
                category_dist[d.root_cause_category] = category_dist.get(d.root_cause_category, 0) + 1

        # 版本关联的需求统计
        requirements_count = 0
        if version_id is not None:
            requirements_count = self.db.query(func.count(TestRequirement.id)).filter(
                TestRequirement.project_id == project_id,
                TestRequirement.version_id == version_id,
            ).scalar() or 0

        # 版本关联的测试计划统计
        plans_count = 0
        completed_plans = 0
        plan_exec_count = 0
        plan_exec_passed = 0
        plan_exec_failed = 0
        if version_id is not None:
            plans_count = self.db.query(func.count(TestPlan.id)).filter(
                TestPlan.project_id == project_id,
                TestPlan.version_id == version_id,
            ).scalar() or 0
            completed_plans = self.db.query(func.count(TestPlan.id)).filter(
                TestPlan.project_id == project_id,
                TestPlan.version_id == version_id,
                TestPlan.status == "completed",
            ).scalar() or 0
            # 测试计划执行记录统计（基于 TestPlanExecution，统一 TestPlanItem 口径）
            version_plan_ids = [p[0] for p in self.db.query(TestPlan.id).filter(
                TestPlan.project_id == project_id,
                TestPlan.version_id == version_id,
            ).all()]
            if version_plan_ids:
                plan_exec_base = self.db.query(TestPlanExecution).filter(
                    TestPlanExecution.plan_id.in_(version_plan_ids),
                    TestPlanExecution.is_deleted == False,
                )
                plan_exec_count = plan_exec_base.count()
                plan_exec_passed = plan_exec_base.filter(TestPlanExecution.status == "completed").count()
                plan_exec_failed = plan_exec_base.filter(TestPlanExecution.status == "failed").count()
        else:
            plan_exec_base = self.db.query(TestPlanExecution).join(
                TestPlan, TestPlan.id == TestPlanExecution.plan_id
            ).filter(
                TestPlan.project_id == project_id,
                TestPlanExecution.is_deleted == False,
            )
            plan_exec_count = plan_exec_base.count()
            plan_exec_passed = plan_exec_base.filter(TestPlanExecution.status == "completed").count()
            plan_exec_failed = plan_exec_base.filter(TestPlanExecution.status == "failed").count()

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
            "total_requirements": requirements_count,
            "total_plans": plans_count,
            "completed_plans": completed_plans,
            "api_total_runs": api_total_runs,
            "api_passed_runs": api_passed_runs,
            "api_failed_runs": api_failed_runs,
            "api_avg_duration": round(api_avg_duration, 2),
            "plan_exec_count": plan_exec_count,
            "plan_exec_passed": plan_exec_passed,
            "plan_exec_failed": plan_exec_failed,
        }

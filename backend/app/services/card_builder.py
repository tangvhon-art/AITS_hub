"""
飞书消息卡片构建器

按需求文档 4.2 实现 14 种卡片模板，统一卡片结构：
- header(title + template 颜色)
- column_set(触发人 + 触发时间)
- markdown(事件详情)
- hr
- action(跳转按钮)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _front_url(path: str) -> str:
    """拼接前端完整 URL"""
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}{path}"


def _format_duration(seconds: Optional[float]) -> str:
    """将秒数格式化为易读时长"""
    if seconds is None:
        return "-"
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "-"
    if seconds < 60:
        return f"{seconds:.1f}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}分{secs}秒"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}小时{minutes}分{secs}秒"


def _truncate(text: Any, max_len: int = 200) -> str:
    """截断文本"""
    if text is None:
        return ""
    s = str(text)
    return s if len(s) <= max_len else s[:max_len] + "..."


class CardBuilder:
    """飞书消息卡片构建器"""

    # 事件级别 → 卡片颜色
    LEVEL_COLORS = {
        "success": "green",
        "info": "blue",
        "warning": "orange",
        "error": "red",
    }

    # ==================== 统一入口 ====================

    @classmethod
    def build(cls, event_code: str, context: Dict[str, Any], triggered_by: Optional[str] = None) -> Dict[str, Any]:
        """
        根据事件编码和上下文构建飞书卡片

        Args:
            event_code: 事件编码
            context: 事件上下文数据
            triggered_by: 触发人名称

        Returns:
            飞书 interactive card 的 card 部分（不含 msg_type 外壳）
        """
        builder_map = {
            "plan.execution.completed": cls.build_plan_completed,
            "plan.execution.failed": cls.build_plan_failed,
            "api.scenario.completed": cls.build_scenario_completed,
            "ui.suite.completed": cls.build_suite_completed,
            "ui.script.failed": cls.build_script_failed,
            "performance.completed": cls.build_performance_completed,
            "ai.requirement.generated": cls.build_ai_requirement,
            "ai.case.generated": cls.build_ai_case,
            "ai.api_case.generated": cls.build_ai_api_case,
            "ai.api_doc.generated": cls.build_ai_api_doc,
            "ai.report.generated": cls.build_ai_report,
            "ai.task.failed": cls.build_ai_task_failed,
            "defect.created": cls.build_defect_created,
            "defect.assigned": cls.build_defect_assigned,
            "defect.resolved": cls.build_defect_status_changed,
            "defect.closed": cls.build_defect_status_changed,
            "defect.reopened": cls.build_defect_status_changed,
            "knowledge.doc_processed": cls.build_knowledge_processed,
            "api.import.completed": cls.build_api_import_completed,
        }
        builder = builder_map.get(event_code)
        if not builder:
            logger.warning(f"未知事件编码，使用默认卡片: {event_code}")
            return cls._build_default_card(event_code, context, triggered_by)
        try:
            return builder(context, triggered_by)
        except Exception as e:
            logger.exception(f"构建卡片失败 event={event_code}: {e}")
            return cls._build_default_card(event_code, context, triggered_by)

    # ==================== 卡片骨架 ====================

    @classmethod
    def _card(
        cls,
        title: str,
        template: str,
        detail_lines: List[str],
        triggered_by: Optional[str],
        buttons: List[Dict[str, Any]],
        trigger_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建统一卡片结构"""
        trigger_time = trigger_time or datetime.now().strftime("%Y-%m-%d %H:%M")
        trigger_person = triggered_by or "系统"

        elements: List[Dict[str, Any]] = [
            {
                "tag": "column_set",
                "flex_mode": "none",
                "horizontal_spacing": "8px",
                "columns": [
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "elements": [
                            {"tag": "markdown", "content": f"**触发人**\n{trigger_person}"}
                        ],
                    },
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "elements": [
                            {"tag": "markdown", "content": f"**触发时间**\n{trigger_time}"}
                        ],
                    },
                ],
            },
            {
                "tag": "markdown",
                "content": "**事件详情**\n" + "\n".join(detail_lines),
            },
        ]

        if buttons:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": buttons,
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": _truncate(title, 100)},
                "template": template,
            },
            "elements": elements,
        }

    @classmethod
    def _button(cls, text: str, url: str, btn_type: str = "primary") -> Dict[str, Any]:
        """构建跳转按钮"""
        return {
            "tag": "button",
            "text": {"tag": "plain_text", "content": text},
            "type": btn_type,
            "url": url,
        }

    @classmethod
    def _build_default_card(cls, event_code: str, context: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        """未知事件的兜底卡片"""
        lines = [f"事件编码：{event_code}"]
        for k, v in (context or {}).items():
            if k in ("project_id",):
                continue
            lines.append(f"{k}：{_truncate(v, 100)}")
        return cls._card(
            title=f"📢 通知 - {event_code}",
            template="blue",
            detail_lines=lines,
            triggered_by=triggered_by,
            buttons=[],
        )

    # ==================== 4.2.1 测试计划执行完成 ====================

    @classmethod
    def build_plan_completed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        return cls._build_plan_card(ctx, triggered_by, failed=False)

    @classmethod
    def build_plan_failed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        return cls._build_plan_card(ctx, triggered_by, failed=True)

    @classmethod
    def _build_plan_card(cls, ctx: Dict[str, Any], triggered_by: Optional[str], failed: bool) -> Dict[str, Any]:
        plan_name = ctx.get("plan_name", "未知计划")
        project_id = ctx.get("project_id")
        plan_id = ctx.get("plan_id")
        execution_id = ctx.get("execution_id")
        env_name = ctx.get("environment_name", "默认环境")
        total = ctx.get("total_count", ctx.get("total_items", 0))
        passed = ctx.get("passed_count", 0)
        failed_count = ctx.get("failed_count", 0)
        skipped = ctx.get("skipped_count", 0)
        pass_rate = ctx.get("pass_rate", 0)
        duration = ctx.get("duration", ctx.get("total_duration", 0))
        failed_nodes = ctx.get("failed_nodes", []) or []

        title = f"{'⚠️' if failed else '✅'} 测试计划执行{'有失败' if failed else '完成'} - {plan_name}"
        template = "orange" if failed else "green"

        lines = [
            f"计划名称：{plan_name}",
            f"执行环境：{env_name}",
            f"总节点数：{total} ｜ 通过：{passed} ｜ 失败：{failed_count} ｜ 跳过：{skipped}",
            f"通过率：{pass_rate}%",
            f"耗时：{_format_duration(duration)}",
        ]
        if failed_nodes:
            shown = failed_nodes[:5]
            names = "、".join(str(n) for n in shown)
            if len(failed_nodes) > 5:
                names += f" 等 {len(failed_nodes)} 个"
            lines.append(f"失败节点：{names}")

        buttons = []
        if project_id and plan_id and execution_id:
            buttons.append(cls._button(
                "查看执行详情",
                _front_url(f"/projects/{project_id}/test-plans/{plan_id}/run/{execution_id}"),
            ))
        elif project_id:
            buttons.append(cls._button("查看测试计划", _front_url(f"/projects/{project_id}/plans")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.2 缺陷创建 ====================

    @classmethod
    def build_defect_created(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        title_text = ctx.get("title", "未命名缺陷")
        project_id = ctx.get("project_id")
        severity = ctx.get("severity", "-")
        priority = ctx.get("priority", "-")
        module = ctx.get("module_name", ctx.get("module", "-"))
        creator = ctx.get("creator_name", triggered_by or "-")
        related = ctx.get("related", "-")

        title = f"🐛 新缺陷：{title_text}"
        lines = [
            f"缺陷标题：{title_text}",
            f"严重程度：{severity}",
            f"优先级：{priority}",
            f"所属模块：{module}",
            f"创建人：{creator}",
        ]
        if related and related != "-":
            lines.append(f"关联用例/执行：{related}")

        buttons = []
        if project_id:
            defect_id = ctx.get("defect_id")
            if defect_id:
                buttons.append(cls._button("查看缺陷", _front_url(f"/projects/{project_id}/defects")))
            else:
                buttons.append(cls._button("查看缺陷列表", _front_url(f"/projects/{project_id}/defects")))

        return cls._card(title, "red", lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.3 接口场景执行完成 ====================

    @classmethod
    def build_scenario_completed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        scenario_name = ctx.get("scenario_name", "未知场景")
        project_id = ctx.get("project_id")
        execution_id = ctx.get("execution_id")
        env_name = ctx.get("environment_name", "默认环境")
        total = ctx.get("total_steps", 0)
        passed = ctx.get("passed_steps", 0)
        failed = ctx.get("failed_steps", 0)
        duration = ctx.get("total_duration", ctx.get("duration", 0))
        has_failure = failed > 0

        title = f"🔗 接口场景执行完成 - {scenario_name}"
        template = "orange" if has_failure else "green"
        lines = [
            f"场景名称：{scenario_name}",
            f"环境：{env_name}",
            f"总步骤：{total} ｜ 通过：{passed} ｜ 失败：{failed}",
            f"耗时：{_format_duration(duration)}",
        ]
        buttons = []
        if project_id and execution_id:
            buttons.append(cls._button(
                "查看执行记录",
                _front_url(f"/projects/{project_id}/api-test/executions/{execution_id}"),
            ))
        elif project_id:
            buttons.append(cls._button("查看执行记录", _front_url(f"/projects/{project_id}/api-test/executions")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.4 UI 自动化编排完成 ====================

    @classmethod
    def build_suite_completed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        suite_name = ctx.get("suite_name", "未知套件")
        project_id = ctx.get("project_id")
        run_id = ctx.get("run_id", ctx.get("suite_run_id"))
        total = ctx.get("total_steps", 0)
        passed = ctx.get("passed_steps", 0)
        failed = ctx.get("failed_steps", 0)
        duration = ctx.get("total_duration", ctx.get("duration", 0))
        ai_fix_count = ctx.get("ai_fix_count", 0)
        has_failure = failed > 0

        title = f"🤖 UI 自动化编排完成 - {suite_name}"
        template = "orange" if has_failure else "green"
        lines = [
            f"套件名称：{suite_name}",
            f"总步骤：{total} ｜ 通过：{passed} ｜ 失败：{failed}",
            f"耗时：{_format_duration(duration)}",
            f"AI 修复次数：{ai_fix_count}",
        ]
        buttons = []
        if project_id and run_id:
            buttons.append(cls._button("查看执行详情", _front_url(f"/projects/{project_id}/suite-runs/{run_id}")))
        elif project_id:
            buttons.append(cls._button("查看编排", _front_url(f"/projects/{project_id}/suites")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.5 性能测试完成 ====================

    @classmethod
    def build_performance_completed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        test_name = ctx.get("test_name", "未知性能测试")
        project_id = ctx.get("project_id")
        test_id = ctx.get("test_id")
        run_id = ctx.get("run_id")
        vus = ctx.get("virtual_users", ctx.get("concurrency", 0))
        duration_s = ctx.get("duration", ctx.get("hold_seconds", 0))
        total_requests = ctx.get("total_requests", 0)
        rps = ctx.get("rps", ctx.get("requests_per_second", 0))
        avg_rt = ctx.get("avg_response_time", 0)
        p95 = ctx.get("p95_response_time", 0)
        p99 = ctx.get("p99_response_time", 0)
        failure_rate = ctx.get("failure_rate", 0)

        title = f"⚡ 性能测试完成 - {test_name}"
        lines = [
            f"测试名称：{test_name}",
            f"并发用户：{vus} ｜ 持续时间：{_format_duration(duration_s)}",
            f"总请求数：{total_requests} ｜ RPS：{rps}",
            f"平均响应：{avg_rt}ms ｜ P95：{p95}ms ｜ P99：{p99}ms",
            f"失败率：{failure_rate}%",
        ]
        buttons = []
        if project_id and test_id:
            buttons.append(cls._button(
                "查看性能报告",
                _front_url(f"/projects/{project_id}/performance-tests/{test_id}/runs"),
            ))
        elif project_id:
            buttons.append(cls._button("查看性能测试", _front_url(f"/projects/{project_id}/performance-tests")))

        return cls._card(title, "blue", lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.6 AI 需求生成完成 ====================

    @classmethod
    def build_ai_requirement(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        req_title = ctx.get("requirement_title", ctx.get("title", "未知需求"))
        project_id = ctx.get("project_id")
        version_name = ctx.get("version_name", "-")
        success = ctx.get("success", True)
        duration = ctx.get("duration", 0)
        error = ctx.get("error", "")

        title = f"📝 AI 需求生成完成 - {req_title}"
        template = "green" if success else "red"
        lines = [
            f"需求标题：{req_title}",
            f"关联版本：{version_name}",
            f"生成状态：{'成功' if success else '失败'}",
            f"耗时：{_format_duration(duration)}",
        ]
        if not success and error:
            lines.append(f"错误原因：{_truncate(error)}")
        buttons = []
        if project_id:
            buttons.append(cls._button("查看需求", _front_url(f"/projects/{project_id}/requirements")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.7 AI 用例生成完成（功能/接口通用） ====================

    @classmethod
    def build_ai_case(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        return cls._build_ai_case_card(ctx, triggered_by, source_type_label="需求", is_api=False)

    @classmethod
    def build_ai_api_case(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        return cls._build_ai_case_card(ctx, triggered_by, source_type_label="接口", is_api=True)

    @classmethod
    def _build_ai_case_card(cls, ctx: Dict[str, Any], triggered_by: Optional[str], source_type_label: str, is_api: bool) -> Dict[str, Any]:
        source_name = ctx.get("source_name", "未知来源")
        project_id = ctx.get("project_id")
        strategy = ctx.get("strategy", "comprehensive")
        success_count = ctx.get("success_count", ctx.get("generated_count", 0))
        failed_count = ctx.get("failed_count", 0)
        duration = ctx.get("duration", 0)
        total = success_count + failed_count

        strategy_map = {
            "normal": "正常", "exception": "异常", "boundary": "边界",
            "comprehensive": "全面", "standard": "标准",
        }
        strategy_label = strategy_map.get(strategy, strategy)

        if total > 0 and failed_count == 0:
            template = "green"
        elif success_count > 0 and failed_count > 0:
            template = "orange"
        elif total > 0 and success_count == 0:
            template = "red"
        else:
            template = "blue"

        title = f"🧪 AI 用例生成完成 - {source_name}"
        lines = [
            f"来源类型：{source_type_label}",
            f"来源名称：{source_name}",
            f"生成策略：{strategy_label}",
            f"生成数量：成功 {success_count} ｜ 失败 {failed_count}",
            f"耗时：{_format_duration(duration)}",
        ]
        buttons = []
        if project_id:
            if is_api:
                buttons.append(cls._button("查看接口用例", _front_url(f"/projects/{project_id}/api-test/cases")))
            else:
                buttons.append(cls._button("查看用例列表", _front_url(f"/projects/{project_id}/cases")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.8 AI 接口文档生成完成 ====================

    @classmethod
    def build_ai_api_doc(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        api_name = ctx.get("api_name", "未知接口")
        project_id = ctx.get("project_id")
        api_id = ctx.get("api_id")
        method = (ctx.get("method") or "").upper()
        path = ctx.get("path", "")
        success = ctx.get("success", True)
        duration = ctx.get("duration", 0)
        error = ctx.get("error", "")

        title = f"📄 AI 接口文档生成完成 - {api_name}"
        template = "green" if success else "red"
        lines = [
            f"接口名称：{api_name}",
        ]
        if method or path:
            lines.append(f"请求信息：{method} {path}")
        lines.append(f"生成状态：{'成功' if success else '失败'}")
        lines.append(f"耗时：{_format_duration(duration)}")
        if not success and error:
            lines.append(f"错误原因：{_truncate(error)}")

        buttons = []
        if project_id and api_id:
            buttons.append(cls._button(
                "查看接口",
                _front_url(f"/projects/{project_id}/api-test/definitions/{api_id}"),
            ))
        elif project_id:
            buttons.append(cls._button("查看接口列表", _front_url(f"/projects/{project_id}/api-test/definitions")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.9 AI 测试报告生成完成 ====================

    @classmethod
    def build_ai_report(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        report_name = ctx.get("report_name", ctx.get("title", "测试报告"))
        project_id = ctx.get("project_id")
        report_id = ctx.get("report_id")
        version_name = ctx.get("version_name", "-")
        period = ctx.get("period", ctx.get("report_period", "-"))
        pass_rate = ctx.get("pass_rate", 0)
        defect_count = ctx.get("defect_count", 0)

        title = f"📊 AI 测试报告生成完成 - {report_name}"
        lines = [
            f"报告名称：{report_name}",
            f"关联版本：{version_name}",
            f"报告周期：{period}",
            f"通过率：{pass_rate}%",
            f"缺陷数：{defect_count}",
        ]
        buttons = []
        if project_id:
            buttons.append(cls._button("查看报告", _front_url(f"/projects/{project_id}/reports")))

        return cls._card(title, "blue", lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.10 AI 任务失败（通用） ====================

    @classmethod
    def build_ai_task_failed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        task_type = ctx.get("task_type", ctx.get("task_name", "未知任务"))
        project_id = ctx.get("project_id")
        related = ctx.get("related_object", ctx.get("related", "-"))
        error = ctx.get("error", ctx.get("error_message", "未知错误"))

        title = f"❌ AI 任务失败 - {task_type}"
        lines = [
            f"任务类型：{task_type}",
            f"关联对象：{related}",
            f"失败原因：{_truncate(error)}",
            f"失败时间：{ctx.get('trigger_time') or datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        buttons = []
        if project_id:
            buttons.append(cls._button("查看任务详情", _front_url(f"/agent-tasks")))

        return cls._card(title, "red", lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.11 缺陷状态变更 ====================

    @classmethod
    def build_defect_assigned(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        """缺陷分配"""
        title_text = ctx.get("title", "未命名缺陷")
        project_id = ctx.get("project_id")
        assignee = ctx.get("assignee_name", "-")
        severity = ctx.get("severity", "-")

        title = f"📌 缺陷分配 - {title_text}"
        lines = [
            f"缺陷标题：{title_text}",
            f"负责人：{assignee}",
            f"严重程度：{severity}",
            f"操作人：{triggered_by or '系统'}",
        ]
        buttons = []
        if project_id:
            buttons.append(cls._button("查看缺陷", _front_url(f"/projects/{project_id}/defects")))

        return cls._card(title, "blue", lines, triggered_by, buttons, ctx.get("trigger_time"))

    @classmethod
    def build_defect_status_changed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        """缺陷已解决/已关闭/重新打开（根据 event_code 或 ctx.status 判断）"""
        title_text = ctx.get("title", "未命名缺陷")
        project_id = ctx.get("project_id")
        new_status = ctx.get("new_status", ctx.get("status", ""))
        old_status = ctx.get("old_status", "-")
        operator = ctx.get("operator_name", triggered_by or "系统")
        severity = ctx.get("severity", "-")
        assignee = ctx.get("assignee_name", "-")

        status_config = {
            "resolved": ("✅ 缺陷已解决", "green"),
            "closed": ("🔒 缺陷已关闭", "blue"),
            "reopened": ("🔄 缺陷重新打开", "orange"),
        }
        # 兼容中文状态
        status_cn_map = {"已解决": "resolved", "已关闭": "closed", "重新打开": "reopened"}
        status_key = status_cn_map.get(new_status, new_status)
        icon, template = status_config.get(status_key, ("🔄 缺陷状态变更", "blue"))

        status_label_cn = {"resolved": "已解决", "closed": "已关闭", "reopened": "重新打开"}
        old_label = status_label_cn.get(old_status, old_status)
        new_label = status_label_cn.get(status_key, new_status)

        title = f"{icon} - {title_text}"
        lines = [
            f"缺陷标题：{title_text}",
            f"状态变更：{old_label} → {new_label}",
            f"操作人：{operator}",
            f"严重程度：{severity}",
            f"负责人：{assignee}",
        ]
        buttons = []
        if project_id:
            buttons.append(cls._button("查看缺陷", _front_url(f"/projects/{project_id}/defects")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.12 UI 脚本执行失败 ====================

    @classmethod
    def build_script_failed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        script_name = ctx.get("script_name", "未知脚本")
        project_id = ctx.get("project_id")
        run_id = ctx.get("run_id", ctx.get("suite_run_id"))
        failed_step = ctx.get("failed_step", "-")
        error = ctx.get("error", ctx.get("error_message", "未知错误"))
        ai_fix_triggered = ctx.get("ai_fix_triggered", False)
        ai_fix_result = ctx.get("ai_fix_result", "-")
        duration = ctx.get("duration", 0)

        title = f"🤖 UI 脚本执行失败 - {script_name}"
        lines = [
            f"脚本名称：{script_name}",
            f"失败步骤：{failed_step}",
            f"错误信息：{_truncate(error)}",
            f"AI 修复：{'已触发' if ai_fix_triggered else '未触发'}"
            + (f"（{ai_fix_result}）" if ai_fix_triggered and ai_fix_result != "-" else ""),
            f"耗时：{_format_duration(duration)}",
        ]
        buttons = []
        if project_id and run_id:
            buttons.append(cls._button("查看执行记录", _front_url(f"/projects/{project_id}/suite-runs/{run_id}")))
        elif project_id:
            buttons.append(cls._button("查看脚本", _front_url(f"/projects/{project_id}/scripts")))

        return cls._card(title, "orange", lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.13 知识库文档处理完成 ====================

    @classmethod
    def build_knowledge_processed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        doc_name = ctx.get("doc_name", ctx.get("file_name", "未知文档"))
        project_id = ctx.get("project_id")
        file_type = ctx.get("file_type", "-")
        file_size = ctx.get("file_size", "-")
        success = ctx.get("success", True)
        chunk_count = ctx.get("chunk_count", 0)
        error = ctx.get("error", "")

        title = f"📚 知识库文档处理完成 - {doc_name}"
        template = "green" if success else "red"
        lines = [
            f"文档名称：{doc_name}",
            f"文件类型/大小：{file_type} / {file_size}",
            f"处理状态：{'向量化成功' if success else '向量化失败'}",
        ]
        if success:
            lines.append(f"分块数量：{chunk_count}")
        elif error:
            lines.append(f"失败原因：{_truncate(error)}")

        buttons = []
        if project_id:
            buttons.append(cls._button("查看知识库", _front_url(f"/projects/{project_id}/knowledge")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

    # ==================== 4.2.14 接口批量导入完成 ====================

    @classmethod
    def build_api_import_completed(cls, ctx: Dict[str, Any], triggered_by: Optional[str]) -> Dict[str, Any]:
        file_name = ctx.get("file_name", "未知文件")
        project_id = ctx.get("project_id")
        import_type = (ctx.get("import_type") or "").upper()
        created = ctx.get("created_count", ctx.get("new_count", 0))
        updated = ctx.get("updated_count", 0)
        failed = ctx.get("failed_count", 0)
        errors = ctx.get("errors", []) or []

        type_map = {
            "POSTMAN": "Postman", "SWAGGER": "Swagger", "JMETER": "JMeter",
            "HAR": "HAR", "APIFOX": "Apifox", "OPENAPI": "Swagger",
        }
        type_label = type_map.get(import_type, import_type or "-")

        total = created + updated + failed
        if total > 0 and failed == 0:
            template = "green"
        elif created + updated > 0 and failed > 0:
            template = "orange"
        elif total > 0 and created + updated == 0:
            template = "red"
        else:
            template = "blue"

        title = f"📥 接口导入完成 - {file_name}"
        lines = [
            f"文件名：{file_name}",
            f"导入格式：{type_label}",
            f"导入结果：新增 {created} ｜ 更新 {updated} ｜ 失败 {failed}",
        ]
        if errors:
            shown = errors[:3]
            err_text = "；".join(_truncate(e, 80) for e in shown if isinstance(e, str))
            if len(errors) > 3:
                err_text += f" 等 {len(errors)} 条"
            lines.append(f"失败摘要：{err_text}")

        buttons = []
        if project_id:
            buttons.append(cls._button("查看接口列表", _front_url(f"/projects/{project_id}/api-test/definitions")))

        return cls._card(title, template, lines, triggered_by, buttons, ctx.get("trigger_time"))

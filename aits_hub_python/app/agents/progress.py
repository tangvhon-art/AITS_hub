"""进度事件推送辅助函数"""
import time
from typing import Any, Dict, List, Optional


def progress(node: str, label: str, status: str = "running", detail: Optional[str] = None) -> Dict[str, Any]:
    """构建进度事件"""
    event = {"type": "progress", "node": node, "label": label, "status": status}
    if detail:
        event["detail"] = detail
    return event


# 标准进度节点常量
class ProgressNode:
    INTENT_RECOGNITION = "intent_recognition"
    KNOWLEDGE_SEARCH = "knowledge_search"
    SKILL_MATCHED = "skill_matched"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    TOOL_DONE = "tool_done"
    GENERATING = "generating"
    ORGANIZING = "organizing"
    DONE = "done"


# 基于意图的进度计划模板
INTENT_PROGRESS_PLAN = {
    "data_query": [
        {"node": "intent", "label": "解析查询意图"},
        {"node": "knowledge", "label": "检索相关知识", "optional": True},
        {"node": "tool_plan", "label": "确定查询数据源"},
        {"node": "tool_call", "label": "执行数据查询", "dynamic": True},
        {"node": "organize", "label": "整理查询结果"},
        {"node": "answer", "label": "生成回答"},
    ],
    "action": [
        {"node": "intent", "label": "解析操作意图"},
        {"node": "validate", "label": "校验操作参数"},
        {"node": "tool_call", "label": "执行操作", "dynamic": True},
        {"node": "verify", "label": "验证执行结果"},
        {"node": "answer", "label": "生成操作反馈"},
    ],
    "knowledge": [
        {"node": "intent", "label": "解析问题"},
        {"node": "knowledge", "label": "知识库向量检索"},
        {"node": "rerank", "label": "相关度排序"},
        {"node": "answer", "label": "基于知识生成回答"},
    ],
    "chat": [
        {"node": "intent", "label": "理解问题"},
        {"node": "answer", "label": "思考并回答"},
    ],
}

# 工具中文名映射（用于动态进度文案）
TOOL_LABELS = {
    "query_project_stats": "项目统计",
    "list_projects": "查询项目列表",
    "list_cases": "查询用例",
    "list_defects": "查询缺陷",
    "analyze_defects": "缺陷分析",
    "search_knowledge": "知识库检索",
    "create_defect": "创建缺陷",
    "list_api_cases": "查询接口用例",
    "list_test_plans": "查询测试计划",
    "list_scripts": "查询脚本",
    "list_versions": "查询版本",
    "list_requirements": "查询需求",
    "list_reports": "查询报告",
    "list_api_definitions": "查询接口定义",
    "list_api_scenarios": "查询接口场景",
    "list_api_executions": "查询执行记录",
    "query_quality_metrics": "质量指标",
}


def get_tool_label(tool_name: str) -> str:
    """获取工具中文名，MCP 工具显示来源标签"""
    if "__" in tool_name:
        connector, name = tool_name.split("__", 1)
        return f"[{connector}] {TOOL_LABELS.get(name, name)}"
    return TOOL_LABELS.get(tool_name, tool_name)


def build_tool_step_label(tool_name: str, args: Dict[str, Any]) -> str:
    """根据工具名和参数生成人类可读的进度步骤描述"""
    # MCP 工具
    if "__" in tool_name:
        connector, name = tool_name.split("__", 1)
        return f"调用 [{connector}] 工具：{TOOL_LABELS.get(name, name)}"
    # Skill 脚本工具
    if tool_name.startswith("skill_"):
        parts = tool_name.split("_", 2)
        return f"执行 Skill 脚本：{parts[-1] if len(parts) > 2 else tool_name}"
    # 内置工具，带参数详情
    detail_map = {
        "list_cases": f"查询用例（需求ID: {args.get('req_id', '全部')}）",
        "list_defects": f"查询缺陷（状态: {args.get('status', '全部')}）",
        "list_requirements": f"查询需求（关键词: {args.get('keyword', '无') or '无'}）",
        "list_api_definitions": f"查询接口定义（方法: {args.get('method', '全部')}）",
        "search_knowledge": f"知识库检索（{(args.get('query', '') or '')[:20]}）",
        "create_defect": f"创建缺陷（{(args.get('title', '') or '')[:20]}）",
        "list_projects": "查询项目列表",
        "query_project_stats": "查询项目统计",
        "query_quality_metrics": "查询质量指标",
        "list_test_plans": "查询测试计划",
        "list_scripts": "查询自动化脚本",
        "list_versions": "查询项目版本",
        "list_reports": "查询测试报告",
        "list_api_cases": "查询接口用例",
        "list_api_scenarios": "查询接口场景",
        "list_api_executions": "查询执行记录",
        "analyze_defects": "缺陷智能分析",
    }
    return detail_map.get(tool_name, f"调用工具：{tool_name}")


class ProgressManager:
    """动态进度管理器：基于意图预生成步骤计划，逐步推进状态"""

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self._step_index: Dict[str, int] = {}
        self._tool_step_count = 0

    def init_plan(self, intent: str, use_knowledge: bool = False,
                  skill_name: Optional[str] = None) -> Dict[str, Any]:
        """根据意图初始化进度计划，全部设为 pending"""
        plan = INTENT_PROGRESS_PLAN.get(intent, INTENT_PROGRESS_PLAN["chat"])
        self.steps = []
        self._step_index.clear()
        self._tool_step_count = 0

        for step in plan:
            if step.get("optional") and not use_knowledge:
                continue
            step_data = {
                "node": step["node"],
                "label": step["label"],
                "status": "pending",
                "duration": None,
                "dynamic": step.get("dynamic", False),
            }
            self._step_index[step["node"]] = len(self.steps)
            self.steps.append(step_data)

        # Skill 匹配成功时插入步骤
        if skill_name:
            self._insert_after("intent", {
                "node": "skill",
                "label": f"加载能力：{skill_name}",
                "status": "pending",
            })

        return self.snapshot()

    def _insert_after(self, after_node: str, new_step: Dict[str, Any]):
        """在指定节点后插入步骤"""
        idx = self._step_index.get(after_node)
        if idx is not None:
            self.steps.insert(idx + 1, new_step)
            # 重建索引
            self._rebuild_index()

    def _rebuild_index(self):
        self._step_index.clear()
        for i, step in enumerate(self.steps):
            self._step_index[step["node"]] = i

    def start(self, node: str, label: Optional[str] = None) -> Dict[str, Any]:
        """标记步骤为 running，可动态覆盖 label"""
        idx = self._step_index.get(node)
        if idx is not None:
            self.steps[idx]["status"] = "running"
            if label:
                self.steps[idx]["label"] = label
            self.steps[idx]["_start_time"] = time.time()
        return self.snapshot()

    def done(self, node: str) -> Dict[str, Any]:
        """标记步骤为 done，计算耗时"""
        idx = self._step_index.get(node)
        if idx is not None:
            self.steps[idx]["status"] = "done"
            start = self.steps[idx].pop("_start_time", None)
            if start:
                self.steps[idx]["duration"] = f"{round(time.time() - start, 1)}s"
        return self.snapshot()

    def add_tool_step(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """追加一个工具调用步骤（多轮工具调用时逐个追加），返回 node id"""
        self._tool_step_count += 1
        node_id = f"tool_{self._tool_step_count}"
        label = build_tool_step_label(tool_name, tool_args)
        step = {
            "node": node_id,
            "label": label,
            "status": "running",
            "duration": None,
            "dynamic": True,
            "_start_time": time.time(),
        }
        # 插入到最后一个 answer 步骤之前
        answer_idx = self._step_index.get("answer")
        if answer_idx is not None:
            self.steps.insert(answer_idx, step)
            self._rebuild_index()
        else:
            self.steps.append(step)
            self._step_index[node_id] = len(self.steps) - 1
        return node_id

    def done_tool_step(self, node_id: str):
        """标记工具步骤完成"""
        idx = self._step_index.get(node_id)
        if idx is not None:
            self.steps[idx]["status"] = "done"
            start = self.steps[idx].pop("_start_time", None)
            if start:
                self.steps[idx]["duration"] = f"{round(time.time() - start, 1)}s"

    def snapshot(self) -> Dict[str, Any]:
        """返回完整进度快照（用于 progress_plan 事件）"""
        steps = []
        for s in self.steps:
            step = {k: v for k, v in s.items() if not k.startswith("_")}
            steps.append(step)
        return {"type": "progress_plan", "steps": steps}

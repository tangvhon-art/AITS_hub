"""
需求功能点拆分 Agent
将需求文本拆分为"模块 → 功能点"两级结构
"""
import json
import re
import logging
from typing import Dict, Any, Optional, List

from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.base_agent import BaseAgent
from app.agents.utils import extract_json

logger = logging.getLogger(__name__)

FEATURE_SPLIT_SYSTEM_PROMPT = """你是一名资深需求分析师，擅长将需求文档拆解为清晰的功能模块和功能点。

## 任务
将用户提供的需求文本拆分为"模块 → 功能点"两级结构，确保拆分结果覆盖需求全部内容、模块划分合理、功能点粒度适中且可独立测试验收。

## 输出格式（最高优先级，强制执行）
**仅输出一个合法的 JSON 对象，禁止输出任何前言、解释、思考过程、Markdown代码块、注释文字。**

根key固定为 "modules"，值为模块数组；每个模块包含 features 功能点数组。所有字段严格按照下方定义生成，**禁止新增或删除任何字段**。

格式：
{"modules": [{"module_name": "模块名", "module_desc": "模块一句话描述", "features": [{"name": "功能点名称", "description": "功能点详细描述，包含业务规则和约束", "priority": "P0", "design_methods": ["等价类划分", "边界值分析"], "preconditions": "前置条件"}]}]}

## 字段强制约束
1. module_name：模块名称，按业务功能域命名（如"用户认证"、"订单管理"），用词简洁统一，同一需求内模块名不得重复；
2. module_desc：模块一句话描述，概括该模块负责的核心业务，不超过100字；
3. name：功能点名称，采用动宾结构、简洁明确（如"创建用户"、"修改密码"），同一模块内功能点名称禁止重复；
4. description：功能点详细描述，必须包含业务规则、输入约束、核心业务逻辑、异常处理要求，确保测试人员无需回看需求即可据此设计用例，禁止只写功能名称；
5. priority：优先级，**仅允许枚举值** P0 / P1 / P2 / P3：
   - P0：核心业务主流程，阻塞性，必须实现
   - P1：重要功能，高频使用
   - P2：一般功能，低频使用
   - P3：边缘功能，锦上添花
6. design_methods：推荐测试设计方法，**仅允许从下方枚举中选择，可多选（1-3个为宜）**：
   - 等价类划分：输入校验类
   - 边界值分析：数值/长度限制类
   - 判定表：多条件组合类
   - 因果图：条件因果关系类
   - 场景法：业务流程类
   - 状态迁移：状态流转类
   - 错误推测法：异常/易错类
   - 正交试验法：多参数组合类
7. preconditions：执行该功能点测试的前置条件（环境、账号、数据准备等）；无特殊前置条件填写"无"，禁止留空。

示例参考：
{
  "modules": [
    {
      "module_name": "用户认证",
      "module_desc": "负责用户登录、注册与账号安全相关功能",
      "features": [
        {
          "name": "用户登录",
          "description": "用户输入用户名和密码登录系统。业务规则：用户名必填，密码长度6-16位；密码连续错误5次锁定账号30分钟；登录成功跳转首页，失败时提示具体错误原因。",
          "priority": "P0",
          "design_methods": ["等价类划分", "边界值分析", "场景法"],
          "preconditions": "系统已部署，存在已注册的测试账号"
        }
      ]
    }
  ]
}

## JSON 语法约束
1. 输出第一个字符必须是 {，最后一个字符必须是 }；
2. 禁止尾部多余逗号；
3. 字符串内换行使用 \\n 转义；
4. 所有字段名使用英文双引号包裹；
5. design_methods 必须为字符串数组，禁止写成字符串或省略该字段；
6. 所有内容使用中文（priority 仅允许 P0-P3 枚举值）。

## 拆解原则
1. 模块按业务功能域划分（如"用户认证"、"订单管理"），不要按页面或技术层划分；
2. 拆分结果必须满足 MECE（相互独立、完全穷尽）：模块之间职责互不重叠，需求中的每个业务点必须归入且仅归入一个功能点，不得遗漏；
3. 每个功能点应可独立测试、可验收，粒度适中：
   - 太粗："用户管理"（应拆为创建用户、编辑用户、删除用户等）
   - 太细："输入用户名"（应合并到"用户登录"等功能点中）
4. 覆盖全面：先识别核心主流程，再补充异常场景（错误输入、非法操作）、边界条件（最大/最小值、空值、超长）、权限控制（未登录、越权）、数据规则（唯一性、状态流转）等可测试场景；
5. 功能点之间不得重复或高度相似，同一业务规则只归属一个功能点，避免冗余拆分；
6. 优先级按"核心主流程优先"分配：主流程功能点分配 P0，重要异常/高频功能分配 P1，一般功能分配 P2，边缘场景分配 P3；
7. design_methods 依据功能点特征匹配最合适的测试设计方法：输入校验类选等价类划分/边界值分析，多条件组合类选判定表，业务流程类选场景法，状态流转类选状态迁移，异常易错类选错误推测法；
8. 功能点较多时均匀拆分到各模块，禁止单个模块塞入过多功能点；模块数量控制在 2-8 个，每个模块功能点 2-8 个。
"""

FEATURE_SPLIT_HUMAN_TEMPLATE = """## 需求信息
- 需求标题：{title}

## 需求内容
{content}

请将以上需求拆分为模块和功能点，严格按 JSON 格式输出。"""


class FeatureSplitterAgent(BaseAgent):
    """需求功能点拆分 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None, project_id: Optional[int] = None):
        super().__init__(db_session, agent_name="feature_splitter", project_id=project_id, llm_config_id=llm_config_id)

    def run(self, **kwargs) -> Dict[str, Any]:
        return self.split_features(
            title=kwargs.get("title", ""),
            content=kwargs.get("content", ""),
        )

    def split_features(self, title: str, content: str) -> Dict[str, Any]:
        """拆分功能点，返回解析后的模块列表"""
        messages = [
            SystemMessage(content=FEATURE_SPLIT_SYSTEM_PROMPT),
            HumanMessage(content=FEATURE_SPLIT_HUMAN_TEMPLATE.format(
                title=title or "未命名需求",
                content=content or "（无详细内容）",
            )),
        ]

        logger.info(f"开始拆分功能点: {title}, 内容长度: {len(content)}")

        response, token_usage, config_id = self._call_llm(messages, temperature=0.2)

        if token_usage:
            self.token_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += token_usage.get("total_tokens", 0)

        raw = response.content if hasattr(response, "content") else str(response)
        modules = self._parse_modules(raw)

        logger.info(f"功能点拆分完成: {len(modules)} 个模块, {sum(len(m.get('features', [])) for m in modules)} 个功能点")

        return {
            "modules": modules,
            "raw_content": raw,
            "token_usage": self.get_token_usage(),
            "llm_config_id": config_id or self.llm_config_id,
        }

    def _call_llm(self, messages, temperature: float = 0.2):
        """调用 LLM，优先使用工厂方法"""
        from app.agents.llm_factory import llm_factory
        response, token_usage, config_id = llm_factory.call_with_fallback(
            self.db,
            messages=messages,
            preferred_config_id=self.llm_config_id,
            temperature=temperature,
        )
        return response, token_usage, config_id

    @staticmethod
    def _parse_modules(raw: str) -> List[Dict[str, Any]]:
        """解析 LLM 返回的模块 JSON"""
        data = extract_json(raw)
        if not data:
            logger.warning("功能点拆分结果 JSON 解析失败，尝试正则提取")
            return []

        modules = data.get("modules", [])
        if not isinstance(modules, list):
            return []

        result = []
        for i, mod in enumerate(modules):
            if not isinstance(mod, dict):
                continue
            module_name = str(mod.get("module_name", "")).strip()
            if not module_name:
                continue
            features = []
            for j, feat in enumerate(mod.get("features", [])):
                if not isinstance(feat, dict):
                    continue
                name = str(feat.get("name", "")).strip()
                if not name:
                    continue
                methods = feat.get("design_methods", [])
                if isinstance(methods, str):
                    methods = [m.strip() for m in re.split(r"[,，、;；]", methods) if m.strip()]
                elif not isinstance(methods, list):
                    methods = []
                priority = str(feat.get("priority", "P1")).strip().upper()
                if priority not in ("P0", "P1", "P2", "P3"):
                    priority = "P1"
                features.append({
                    "name": name[:200],
                    "description": str(feat.get("description", "")).strip(),
                    "priority": priority,
                    "design_methods": methods,
                    "preconditions": str(feat.get("preconditions", "")).strip(),
                    "sort_order": j,
                })
            if features:
                result.append({
                    "module_name": module_name[:200],
                    "module_desc": str(mod.get("module_desc", "")).strip()[:500],
                    "features": features,
                    "sort_order": i,
                })
        return result

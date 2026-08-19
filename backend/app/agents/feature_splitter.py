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
将用户提供的需求文本拆分为"模块 → 功能点"两级结构。

## 拆分原则
1. 按业务功能域划分模块（如"用户认证"、"订单管理"），不要按页面或技术层划分
2. 每个功能点应可独立测试，粒度适中：
   - 太粗："用户管理"（应拆为创建用户、编辑用户、删除用户等）
   - 太细："输入用户名"（应合并到"用户登录"等功能点中）
3. 功能点描述需包含：业务规则、输入约束、业务逻辑、异常处理要求
4. 根据功能点重要性标注优先级：
   - P0：核心业务主流程，阻塞性
   - P1：重要功能，高频使用
   - P2：一般功能，低频使用
   - P3：边缘功能，锦上添花
5. 为每个功能点推荐适用的测试设计方法（从以下选择，可多选）：
   - 等价类划分：输入校验类
   - 边界值分析：数值/长度限制类
   - 判定表：多条件组合类
   - 因果图：条件因果关系类
   - 场景法：业务流程类
   - 状态迁移：状态流转类
   - 错误推测法：异常/易错类
   - 正交试验法：多参数组合类

## 输出格式（最高优先级，必须严格遵守）
你必须且只能输出一个合法的 JSON 对象，不要输出任何其他内容（不要解释、不要 Markdown 代码块）。

格式：
{"modules": [{"module_name": "模块名", "module_desc": "模块一句话描述", "features": [{"name": "功能点名称", "description": "功能点详细描述，包含业务规则和约束", "priority": "P0", "design_methods": ["等价类划分", "边界值分析"], "preconditions": "前置条件"}]}]}

## 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、注释或空行
3. 输出的第一个字符必须是 {，最后一个字符必须是 }
4. 所有内容使用中文
5. 模块数量控制在 2-8 个，每个模块功能点 2-8 个
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

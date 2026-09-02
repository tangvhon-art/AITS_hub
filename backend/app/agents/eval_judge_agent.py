"""AI 裁判 Agent：对被测模型输出按五维标准打分、成对对比

复用 base_agent 上下文管理与 llm_factory 多模型调用；输出 JSON 结构化打分。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.agents.utils import extract_json

logger = logging.getLogger(__name__)

# 五维评分标准（权重）
JUDGE_DIMENSIONS = [
    {"key": "accuracy", "label": "事实准确性", "weight": 0.30},
    {"key": "relevance", "label": "内容相关性", "weight": 0.25},
    {"key": "logic", "label": "逻辑完整性", "weight": 0.20},
    {"key": "instruction", "label": "指令遵循度", "weight": 0.15},
    {"key": "fluency", "label": "语言流畅度", "weight": 0.10},
]

JUDGE_SYSTEM_PROMPT = """你是一名专业的 AI 模型质量评审裁判。请对"被测模型对用户问题的回答"进行评分。
评分维度（1-5 分，5 为最优）：
- accuracy 事实准确性（权重30%）：无虚假信息、无幻觉、知识时效准确、数据无误
- relevance 内容相关性（权重25%）：贴合用户指令、无答非所问、无冗余无关内容
- logic 逻辑完整性（权重20%）：推理通顺、结构完整、论据充分、无逻辑矛盾
- instruction 指令遵循度（权重15%）：满足格式、字数、场景、特殊约束要求
- fluency 语言流畅度（权重10%）：语句通顺、表述专业、无语法错误
必须严格输出 JSON（不要输出任何其他文字）：
{"scores": {"accuracy": 4, "relevance": 4, "logic": 3, "instruction": 5, "fluency": 5}, "reason": "简要评分理由", "issues": ["发现的问题点，无则空数组"]}"""


class EvalJudgeAgent(BaseAgent):
    """AI 裁判 Agent"""

    agent_type = "eval_judge"

    def __init__(self, db_session: Session, llm_config_id: Optional[int] = None, **kwargs):
        super().__init__(db_session, llm_config_id=llm_config_id, agent_name="eval_judge", **kwargs)

    def run(self, **kwargs) -> Dict[str, Any]:
        """统一入口：judge()"""
        return self.judge(
            prompt=kwargs.get("prompt", ""),
            model_output=kwargs.get("model_output", ""),
            expected_output=kwargs.get("expected_output"),
            constraints=kwargs.get("constraints"),
            temperature=kwargs.get("temperature", 0.2),
        )

    def judge(
        self,
        prompt: str,
        model_output: str,
        expected_output: Optional[str] = None,
        constraints: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """对单条用例打分，返回 {scores, weighted_score, reason, issues, dimension_scores}"""
        user_content = f"【用户输入】\n{prompt}\n\n【被测模型输出】\n{model_output}"
        if expected_output:
            user_content += f"\n\n【预期输出参考】\n{expected_output}"
        if constraints:
            user_content += f"\n\n【约束条件】\n{constraints}"
        try:
            response = self._call_llm(
                [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
            )
            content = response.content if hasattr(response, "content") else str(response)
            data = extract_json(str(content)) or {}
        except Exception as e:
            logger.warning(f"裁判打分 LLM 调用失败: {e}")
            data = {}

        scores = data.get("scores") or {}
        # 兜底：缺省维度按 3 分
        normalized = {}
        for d in JUDGE_DIMENSIONS:
            raw = scores.get(d["key"])
            try:
                normalized[d["key"]] = max(1, min(5, int(float(raw)))) if raw is not None else 3
            except (TypeError, ValueError):
                normalized[d["key"]] = 3
        weighted = round(
            sum(normalized[d["key"]] * d["weight"] for d in JUDGE_DIMENSIONS), 2
        )
        return {
            "scores": normalized,
            "weighted_score": weighted,
            "reason": (data.get("reason") or "")[:1000],
            "issues": (data.get("issues") or [])[:10],
        }

    def judge_pair(self, prompt: str, output_a: str, output_b: str, **kw) -> Dict[str, Any]:
        """成对对比：判定 A/B 胜负"""
        user_content = (
            f"【用户输入】\n{prompt}\n\n【模型A输出】\n{output_a}\n\n【模型B输出】\n{output_b}\n"
            "请比较 A、B 两个输出的整体质量，输出 JSON：{\"winner\": \"A\"|\"B\"|\"tie\", \"reason\": \"理由\"}"
        )
        try:
            response = self._call_llm(
                [
                    {"role": "system", "content": "你是严格的模型输出对比裁判，只输出 JSON。"},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
            )
            content = response.content if hasattr(response, "content") else str(response)
            data = extract_json(str(content)) or {}
        except Exception as e:
            logger.warning(f"成对对比调用失败: {e}")
            data = {}
        return {
            "winner": data.get("winner", "tie"),
            "reason": (data.get("reason") or "")[:1000],
        }

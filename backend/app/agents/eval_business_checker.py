"""业务落地测评 Agent：按业务预期输出与约束条件判定成功/失败（规则 + LLM 双路，避免误判）"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.agents.utils import extract_json

logger = logging.getLogger(__name__)


class EvalBusinessChecker(BaseAgent):
    """业务判定 Agent"""

    agent_type = "eval_business_checker"

    def __init__(self, db_session: Session, llm_config_id: Optional[int] = None, **kwargs):
        super().__init__(db_session, llm_config_id=llm_config_id, agent_name="eval_business_checker", **kwargs)

    def run(self, **kwargs) -> Dict[str, Any]:
        """统一入口：check()"""
        return self.check(
            prompt=kwargs.get("prompt", ""),
            model_output=kwargs.get("model_output", ""),
            expected_output=kwargs.get("expected_output"),
            constraints=kwargs.get("constraints"),
        )

    def check(
        self,
        prompt: str,
        model_output: str,
        expected_output: Optional[str] = None,
        constraints: Optional[str] = None,
    ) -> Dict[str, Any]:
        """业务判定：success/fail + 原因。规则 + LLM 双路，任一通过判成功。"""
        out = model_output or ""
        expected = expected_output or ""
        # ── 规则路 ──
        rule_pass = True
        rule_reason = []
        if expected:
            # 期望关键字命中判定
            keywords = [k.strip() for k in expected.replace("，", ",").split(",") if k.strip()]
            if keywords:
                hit_cnt = sum(1 for k in keywords if k in out)
                rule_pass = hit_cnt >= max(1, len(keywords) // 2)
                rule_reason.append(f"期望关键字命中 {hit_cnt}/{len(keywords)}")
        if constraints:
            for c in [x.strip() for x in constraints.replace("，", ",").split(",") if x.strip()]:
                if c and c not in out:
                    rule_reason.append(f"未满足约束: {c}")
        if not out.strip():
            rule_pass = False
            rule_reason.append("输出为空")

        # ── LLM 路 ──
        llm_pass = None
        try:
            response = self._call_llm(
                [
                    {"role": "system", "content": "你是业务验收专家。判断模型回答是否满足业务预期与约束。只输出 JSON：{\"pass\": true|false, \"reason\": \"理由\"}"},
                    {"role": "user", "content": f"【业务输入】\n{prompt}\n\n【预期输出/关键点】\n{expected or '(未提供)'}\n\n【约束】\n{constraints or '(未提供)'}\n\n【模型输出】\n{out}"},
                ],
                temperature=0.1,
            )
            content = response.content if hasattr(response, "content") else str(response)
            data = extract_json(str(content)) or {}
            llm_pass = data.get("pass")
            llm_reason = (data.get("reason") or "")[:500]
        except Exception as e:
            logger.warning(f"业务判定 LLM 调用失败: {e}")
            llm_reason = "LLM 判定失败，以规则判定为准"

        # 合并：双路任一通过即成功（避免误判）
        if llm_pass is True or rule_pass:
            passed = True
            reason = "；".join(filter(None, rule_reason + ([llm_reason] if llm_pass is True else []))) or "满足业务预期"
        else:
            passed = False
            reason = "；".join(filter(None, rule_reason + [llm_reason])) or "不满足业务预期"
        return {"success": passed, "reason": reason[:1000], "rule_pass": rule_pass, "llm_pass": llm_pass}

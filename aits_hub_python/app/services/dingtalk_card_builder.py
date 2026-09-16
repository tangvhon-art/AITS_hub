"""
钉钉消息卡片构建器

适配器模式：调用飞书 CardBuilder 生成统一卡片内容，再转换为钉钉 actionCard 格式。
钉钉 actionCard 不支持飞书的 column_set 等复杂元素，转换为 markdown 文本 + 单按钮。
"""
import logging
from typing import Any, Dict, List, Optional

from app.services.card_builder import CardBuilder, _truncate

logger = logging.getLogger(__name__)

# 事件级别 → 钉钉 markdown 标题颜色 emoji
LEVEL_EMOJI = {
    "success": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
}


class DingTalkCardBuilder:
    """钉钉消息卡片构建器（适配器）"""

    @classmethod
    def build(cls, event_code: str, context: Dict[str, Any],
              triggered_by: Optional[str] = None) -> Dict[str, Any]:
        """
        根据事件编码和上下文构建钉钉 actionCard

        Returns:
            {"title": str, "text": str, "button_title": str, "button_url": str}
        """
        feishu_card = CardBuilder.build(event_code, context, triggered_by)
        return cls.convert_from_feishu_card(feishu_card)

    @classmethod
    def convert_from_feishu_card(cls, feishu_card: Dict[str, Any]) -> Dict[str, Any]:
        """将飞书卡片格式转换为钉钉 actionCard 参数"""

        # 2. 提取标题
        title = ""
        header = feishu_card.get("header", {})
        if isinstance(header, dict):
            title_obj = header.get("title", {})
            if isinstance(title_obj, dict):
                title = title_obj.get("content", "")

        # 3. 提取模板颜色，映射为 emoji 前缀
        template = header.get("template", "blue") if isinstance(header, dict) else "blue"
        level_map = {"green": "success", "red": "error", "orange": "warning", "blue": "info"}
        level = level_map.get(template, "info")
        emoji = LEVEL_EMOJI.get(level, "ℹ️")

        # 4. 从 elements 中提取 markdown 内容和按钮
        elements = feishu_card.get("elements", [])
        md_lines: List[str] = []
        button_url = ""
        button_title = "查看详情"

        for elem in elements:
            if not isinstance(elem, dict):
                continue
            tag = elem.get("tag")

            if tag == "column_set":
                # 飞书的双列布局（触发人 + 触发时间），转为单行
                columns = elem.get("columns", [])
                parts = []
                for col in columns:
                    col_elems = col.get("elements", []) if isinstance(col, dict) else []
                    for ce in col_elems:
                        if isinstance(ce, dict) and ce.get("tag") == "markdown":
                            content = ce.get("content", "")
                            # 去掉 markdown 加粗，转为普通文本
                            content = content.replace("**", "").replace("\n", "：")
                            parts.append(content.strip())
                if parts:
                    md_lines.append(" > ".join(parts))

            elif tag == "markdown":
                content = elem.get("content", "")
                # 飞书 markdown 兼容钉钉，直接保留
                md_lines.append(content)

            elif tag == "hr":
                md_lines.append("---")

            elif tag == "action":
                actions = elem.get("actions", [])
                if actions and isinstance(actions, list):
                    first_btn = actions[0]
                    if isinstance(first_btn, dict):
                        btn_text = first_btn.get("text", {})
                        if isinstance(btn_text, dict):
                            button_title = btn_text.get("content", "查看详情")
                        button_url = first_btn.get("url", "")

        # 5. 组装钉钉 markdown 文本
        text_parts = []
        if title:
            text_parts.append(f"### {emoji} {title}")
        if md_lines:
            text_parts.append("\n\n".join(md_lines))
        text = "\n\n".join(text_parts) if text_parts else title

        return {
            "title": _truncate(title, 100) or "AITS 通知",
            "text": text,
            "button_title": button_title,
            "button_url": button_url,
        }

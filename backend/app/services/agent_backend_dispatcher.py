"""
执行后端分发决策

按 backend 分流 local/workflow；解析最终执行后端。
v0.7 确认 #5：配置了工作流则默认执行工作流；页面选择优先级高于系统默认。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.services.workflow_config_service import resolve_effective_backend


def resolve_backend(db: Session, module_id: str, project_id: Optional[int],
                    page_choice: Optional[str] = None) -> str:
    """解析最终执行后端：页面选择优先 → 模块配置 → local

    全局开关/Webhook 未启用、或模块未配置连接+agent标识时，强制 local。
    """
    return resolve_effective_backend(db, module_id, project_id, page_choice)

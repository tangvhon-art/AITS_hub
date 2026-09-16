"""
造数工厂 API
- GET /api/data-factory/categories          工具分类与参数 Schema（前端表单 + MCP 展示共用）
- POST /api/data-factory/tools/{tool_name}  统一工具执行入口
- POST /api/data-factory/batch              批量执行
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.services.data_tools import (
    SERVICE_REGISTRY,
    DataToolError,
    execute_tool,
    get_tool_meta,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-factory", tags=["造数工厂"])


def _to_http_error(e: DataToolError) -> HTTPException:
    return HTTPException(
        status_code=e.http_status,
        detail={"code": e.code, "message": e.message, "detail": e.detail},
    )


@router.get("/categories")
def get_categories(
    current_user: User = Depends(get_current_user),
):
    """获取工具分类与工具清单（含参数 Schema）"""
    return {"categories": get_tool_meta(), "total": len(SERVICE_REGISTRY)}


@router.post("/tools/{tool_name}")
def run_tool(
    tool_name: str,
    params: Dict[str, Any] = Body(default={}),
    current_user: User = Depends(get_current_user),
):
    """统一工具执行入口"""
    try:
        result = execute_tool(tool_name, params)
    except DataToolError as e:
        raise _to_http_error(e)
    return {"tool": tool_name, "result": result}


@router.post("/batch")
def run_batch(
    items: List[Dict[str, Any]] = Body(...),
    current_user: User = Depends(get_current_user),
):
    """批量执行多个工具，单项失败不影响其余"""
    if not isinstance(items, list):
        raise HTTPException(400, detail={"code": "INVALID_PARAM", "message": "items 需为数组"})
    results = []
    for item in items:
        name = (item or {}).get("tool", "")
        params = (item or {}).get("params", {})
        try:
            result = execute_tool(name, params)
            results.append({"tool": name, "ok": True, "result": result})
        except DataToolError as e:
            results.append({"tool": name, "ok": False,
                            "error": {"code": e.code, "message": e.message, "detail": e.detail}})
    return results

"""MCP 连接器 API"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mcp_connector import MCPConnector
from app.schemas.mcp import MCPConnectorCreate, MCPConnectorUpdate, MCPConnectorResponse, MCPConnectorListResponse, MCPConnectResult
from app.core.deps import get_current_user
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mcp", tags=["MCP"])


@router.get("/connectors", response_model=MCPConnectorListResponse)
def list_connectors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(MCPConnector).filter(MCPConnector.is_deleted == False)
    if status:
        query = query.filter(MCPConnector.status == status)
    total = query.count()
    items = query.order_by(MCPConnector.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": items}


@router.post("/connectors", response_model=MCPConnectorResponse)
def create_connector(data: MCPConnectorCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    connector = MCPConnector(
        name=data.name, description=data.description, transport=data.transport,
        url=data.url, command=data.command, args=data.args, env_vars=data.env_vars,
        is_active=data.is_active, created_by=current_user.id,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


@router.put("/connectors/{connector_id}", response_model=MCPConnectorResponse)
def update_connector(connector_id: int, data: MCPConnectorUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    connector = db.query(MCPConnector).filter(MCPConnector.id == connector_id, MCPConnector.is_deleted == False).first()
    if not connector:
        raise HTTPException(404, "连接器不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(connector, field, value)
    db.commit()
    db.refresh(connector)
    return connector


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    connector = db.query(MCPConnector).filter(MCPConnector.id == connector_id, MCPConnector.is_deleted == False).first()
    if not connector:
        raise HTTPException(404, "连接器不存在")
    connector.is_deleted = True
    connector.deleted_at = china_now_naive()
    db.commit()
    return {"message": "删除成功"}


@router.post("/connectors/{connector_id}/connect", response_model=MCPConnectResult)
async def connect_connector(connector_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """测试连接并拉取工具列表"""
    connector = db.query(MCPConnector).filter(MCPConnector.id == connector_id, MCPConnector.is_deleted == False).first()
    if not connector:
        raise HTTPException(404, "连接器不存在")
    from app.mcp.client import MCPClient
    client = MCPClient(
        connector_id=connector.id, name=connector.name, transport=connector.transport,
        url=connector.url or "", command=connector.command or "", args=connector.args or [],
        env_vars=connector.env_vars or {},
    )
    try:
        tools = await client.connect()
        connector.status = "connected"
        connector.tools_count = len(tools)
        connector.tools_list = [{"name": t.get("name"), "description": t.get("description", "")} for t in tools]
        connector.last_connected_at = china_now_naive()
        connector.error_message = None
        client.register_tools()
        db.commit()
        return {"success": True, "message": "连接成功", "tools_count": len(tools), "tools": connector.tools_list}
    except Exception as e:
        connector.status = "error"
        connector.error_message = str(e)
        db.commit()
        return {"success": False, "message": f"连接失败: {e}", "tools_count": 0, "tools": []}


@router.post("/connectors/{connector_id}/disconnect")
def disconnect_connector(connector_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    connector = db.query(MCPConnector).filter(MCPConnector.id == connector_id, MCPConnector.is_deleted == False).first()
    if not connector:
        raise HTTPException(404, "连接器不存在")
    from app.mcp.client import MCPClient
    client = MCPClient(connector_id=connector.id, name=connector.name, transport=connector.transport)
    client.disconnect()
    connector.status = "disconnected"
    db.commit()
    return {"message": "已断开"}


@router.get("/connectors/{connector_id}/tools")
def get_connector_tools(connector_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    connector = db.query(MCPConnector).filter(MCPConnector.id == connector_id, MCPConnector.is_deleted == False).first()
    if not connector:
        raise HTTPException(404, "连接器不存在")
    return {"tools": connector.tools_list or [], "count": connector.tools_count}


@router.get("/tools")
def list_all_tools(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """列出所有可用工具（内置 + MCP）"""
    from app.agents.tools.registry import tool_registry
    tools = []
    for t in tool_registry.list_tools():
        tools.append({"name": t.name, "description": t.description, "category": t.category,
                      "parameters": t.parameters.to_dict()})
    return {"total": len(tools), "tools": tools}

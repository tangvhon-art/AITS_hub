from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.core.crud import CRUDBase
from app.models.user import User
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse, LLMConfigTestRequest
from app.agents.llm_factory import llm_factory, encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/api/llm-configs", tags=["模型配置管理"])

# 全局资源
llm_config_crud = CRUDBase(LLMConfig, "模型配置")


def _to_response(config: LLMConfig) -> dict:
    """转换为响应对象（隐藏 API Key 明文）"""
    return {
        "id": config.id,
        "name": config.name,
        "provider": config.provider,
        "base_url": config.base_url,
        "model_name": config.model_name,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "streaming": config.streaming,
        "is_default": config.is_default,
        "status": config.status,
        "priority": config.priority,
        "description": config.description,
        "has_api_key": bool(config.api_key),
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.get("", response_model=List[LLMConfigResponse])
def list_llm_configs(
    name: Optional[str] = Query(None, description="配置名称（模糊匹配）"),
    provider: Optional[str] = Query(None, description="提供商"),
    model_name: Optional[str] = Query(None, description="模型名称（模糊匹配）"),
    streaming: Optional[bool] = Query(None, description="是否流式"),
    priority: Optional[int] = Query(None, description="优先级"),
    status: Optional[str] = Query(None, description="状态"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型配置列表（支持筛选）"""
    query = db.query(LLMConfig)
    if name:
        query = query.filter(LLMConfig.name.ilike(f"%{name}%"))
    if provider:
        query = query.filter(LLMConfig.provider == provider)
    if model_name:
        query = query.filter(LLMConfig.model_name.ilike(f"%{model_name}%"))
    if streaming is not None:
        query = query.filter(LLMConfig.streaming == streaming)
    if priority is not None:
        query = query.filter(LLMConfig.priority == priority)
    if status:
        query = query.filter(LLMConfig.status == status)
    configs = query.order_by(LLMConfig.priority.asc()).all()
    return [_to_response(c) for c in configs]


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
def create_llm_config(
    config_data: LLMConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建模型配置"""
    # 检查名称重复
    existing = db.query(LLMConfig).filter(LLMConfig.name == config_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="配置名称已存在")

    # 如果设为默认，取消其他默认
    if config_data.is_default:
        db.query(LLMConfig).filter(LLMConfig.is_default == True).update({"is_default": False})

    config = LLMConfig(
        name=config_data.name,
        provider=config_data.provider,
        base_url=config_data.base_url,
        api_key=encrypt_api_key(config_data.api_key) if config_data.api_key else "",
        model_name=config_data.model_name,
        max_tokens=config_data.max_tokens,
        temperature=config_data.temperature,
        streaming=config_data.streaming,
        is_default=config_data.is_default,
        status=config_data.status,
        priority=config_data.priority,
        description=config_data.description,
    )
    db.add(config)
    db.flush()
    log_audit(
        db, action="create", resource_type="llm_config",
        resource_id=config.id, resource_name=config.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": config.name, "provider": config.provider, "model_name": config.model_name},
    )
    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.get("/{config_id}", response_model=LLMConfigResponse)
def get_llm_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型配置详情"""
    config = llm_config_crud.get(db, config_id)
    return _to_response(config)


@router.put("/{config_id}", response_model=LLMConfigResponse)
def update_llm_config(
    config_id: int,
    config_data: LLMConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模型配置"""
    config = llm_config_crud.get(db, config_id)

    old_data = {"name": config.name, "provider": config.provider, "model_name": config.model_name, "status": config.status}
    update_data = config_data.model_dump(exclude_unset=True)

    # 如果设为默认，取消其他默认
    if update_data.get("is_default"):
        db.query(LLMConfig).filter(LLMConfig.id != config_id, LLMConfig.is_default == True).update({"is_default": False})

    # API Key 加密
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key"] = encrypt_api_key(update_data["api_key"])

    for key, value in update_data.items():
        setattr(config, key, value)
    log_audit(
        db, action="update", resource_type="llm_config",
        resource_id=config.id, resource_name=config.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": {k: v for k, v in update_data.items() if k != "api_key"}},
    )
    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_llm_config(
    config_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模型配置"""
    config = llm_config_crud.get(db, config_id)
    if config.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认模型配置，请先设置其他配置为默认")
    config_name = config.name
    llm_config_crud.soft_delete(db, config_id)
    log_audit(
        db, action="delete", resource_type="llm_config",
        resource_id=config_id, resource_name=config_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/{config_id}/test")
def test_llm_config(
    config_id: int,
    test_data: LLMConfigTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试模型配置连接"""
    config = llm_config_crud.get(db, config_id)

    try:
        # 测试连接强制使用非流式，避免部分自部署模型流式格式不兼容导致报错
        llm = llm_factory.create_llm(
            provider=config.provider,
            model_name=config.model_name,
            base_url=config.base_url,
            api_key=decrypt_api_key(config.api_key),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            streaming=False,
        )
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=test_data.prompt)])
        log_audit(
            db, action="test", resource_type="llm_config",
            resource_id=config.id, resource_name=config.name,
            user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail={"status": "success"},
        )
        db.commit()
        return {
            "status": "success",
            "response": response.content[:500],
            "token_usage": llm_factory._extract_token_usage(response),
        }
    except Exception as e:
        log_audit(
            db, action="test", resource_type="llm_config",
            resource_id=config.id, resource_name=config.name,
            user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failed", error_message=str(e),
        )
        db.commit()
        return {
            "status": "failed",
            "error": str(e),
        }


@router.post("/{config_id}/set-default", response_model=LLMConfigResponse)
def set_default_llm_config(
    config_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置为默认模型"""
    config = llm_config_crud.get(db, config_id)

    db.query(LLMConfig).filter(LLMConfig.is_default == True).update({"is_default": False})
    config.is_default = True
    log_audit(
        db, action="update", resource_type="llm_config",
        resource_id=config.id, resource_name=config.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"field": "is_default", "value": True},
    )
    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.get("/{config_id}/capabilities")
async def get_llm_capabilities(config_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    探测模型能力（缓存24小时）

    检测方式：
    1. Function Calling：发一个带 tools 的实际请求，检查响应是否包含 tool_calls
    2. 流式输出：发一个 stream 请求，检查是否返回流式 chunk
    3. Skill / MCP：依赖 Function Calling，FC 支持则支持
    """
    import time
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id, LLMConfig.is_deleted == False).first()
    if not config:
        raise HTTPException(404, "模型配置不存在")
    now = time.time()
    if config.capabilities and isinstance(config.capabilities, dict):
        detected_at = config.capabilities.get("detected_at", 0)
        if now - detected_at < 86400:
            return config.capabilities

    capabilities = {
        "function_calling": False,
        "streaming": False,
        "skill_supported": False,
        "mcp_supported": False,
        "detected_at": now,
        "probe_method": "actual_request",
    }

    try:
        from app.agents.llm_factory import llm_factory
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = llm_factory.create_llm(config)

        # ---- 1. 探测 Function Calling ----
        # 发一个带 tools 的实际请求，使用 tool_choice="required" 强制模型调用工具
        test_tool = {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "A test tool that returns pong.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
        try:
            # 方式1: tool_choice="required" 强制调用
            try:
                llm_forced = llm.bind_tools([test_tool], tool_choice="required")
                messages = [HumanMessage(content="Please ping now.")]
                response = await llm_forced.ainvoke(messages)
            except Exception:
                # 部分 provider 不支持 tool_choice 参数，降级为普通 bind_tools
                llm_forced = llm.bind_tools([test_tool])
                messages = [
                    SystemMessage(content="You MUST call the ping tool. Do not answer with text."),
                    HumanMessage(content="Ping."),
                ]
                response = await llm_forced.ainvoke(messages)

            # 兼容提取工具调用（同 ChatAgent 的逻辑）
            from app.agents.chat_agent import ChatAgent
            tool_calls = ChatAgent._extract_tool_calls(response)
            has_tool_calls = len(tool_calls) > 0
            capabilities["function_calling"] = has_tool_calls
            if not has_tool_calls:
                capabilities["probe_detail"] = f"模型未返回 tool_calls（response.content={str(response.content)[:100]}）"
        except Exception as e:
            capabilities["function_calling"] = False
            capabilities["probe_error"] = f"FC探测失败: {str(e)[:200]}"

        # ---- 2. 探测流式输出 ----
        try:
            stream_messages = [HumanMessage(content="Say hello in one word.")]
            chunk_count = 0
            async for chunk in llm.astream(stream_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    chunk_count += 1
                if chunk_count >= 2:
                    break
            capabilities["streaming"] = chunk_count > 0
        except Exception as e:
            capabilities["streaming"] = False
            if "probe_error" not in capabilities:
                capabilities["probe_error"] = f"流式探测失败: {str(e)[:200]}"

        # ---- 3. Skill 和 MCP 依赖 Function Calling ----
        capabilities["skill_supported"] = capabilities["function_calling"]
        capabilities["mcp_supported"] = capabilities["function_calling"]

    except Exception as e:
        capabilities["probe_error"] = f"模型连接失败: {str(e)[:200]}"

    config.capabilities = capabilities
    config.supports_function_calling = capabilities["function_calling"]
    db.commit()
    return capabilities

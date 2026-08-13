from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse, LLMConfigTestRequest
from app.agents.llm_factory import llm_factory, encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/api/llm-configs", tags=["模型配置管理"])


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型配置列表"""
    configs = db.query(LLMConfig).order_by(LLMConfig.priority.asc()).all()
    return [_to_response(c) for c in configs]


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
def create_llm_config(
    config_data: LLMConfigCreate,
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
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return _to_response(config)


@router.put("/{config_id}", response_model=LLMConfigResponse)
def update_llm_config(
    config_id: int,
    config_data: LLMConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模型配置"""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    update_data = config_data.model_dump(exclude_unset=True)

    # 如果设为默认，取消其他默认
    if update_data.get("is_default"):
        db.query(LLMConfig).filter(LLMConfig.id != config_id, LLMConfig.is_default == True).update({"is_default": False})

    # API Key 加密
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key"] = encrypt_api_key(update_data["api_key"])

    for key, value in update_data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_llm_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模型配置"""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    if config.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认模型配置，请先设置其他配置为默认")
    db.delete(config)
    db.commit()


@router.post("/{config_id}/test")
def test_llm_config(
    config_id: int,
    test_data: LLMConfigTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试模型配置连接"""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

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
        return {
            "status": "success",
            "response": response.content[:500],
            "token_usage": llm_factory._extract_token_usage(response),
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
        }


@router.post("/{config_id}/set-default", response_model=LLMConfigResponse)
def set_default_llm_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置为默认模型"""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    db.query(LLMConfig).filter(LLMConfig.is_default == True).update({"is_default": False})
    config.is_default = True
    db.commit()
    db.refresh(config)
    return _to_response(config)

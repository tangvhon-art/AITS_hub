"""
通知中心 API（公共模块，全局配置，不隶属于具体项目）

- 渠道 CRUD + 测试发送
- 规则 CRUD
- 事件类型列表
- 发送记录列表/详情/重试
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.deps import get_current_user
from app.database import get_db
from app.models.notification import NotificationChannel, NotificationRecord, NotificationRule
from app.models.user import User
from app.schemas.notification import (
    EventTypeInfo,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationRecordResponse,
    NotificationRuleCreate,
    NotificationRuleResponse,
    NotificationRuleUpdate,
    PaginatedResponse,
    TestSendResult,
)
from app.services.notification_service import EVENT_TYPES, NotificationService, get_event_name

router = APIRouter(prefix="/api/notifications", tags=["通知中心"])


# ==================== 脱敏工具 ====================

def _mask_webhook(url: Optional[str]) -> str:
    """Webhook URL 脱敏：保留协议+域名前缀，隐藏路径中的密钥"""
    if not url:
        return ""
    if len(url) <= 40:
        return url[:20] + "****"
    return url[:35] + "****" + url[-8:]


def _mask_secret(secret: Optional[str]) -> Optional[str]:
    """密钥脱敏：仅显示前4位 + ****"""
    if not secret:
        return None
    try:
        from app.agents.llm_factory import decrypt_api_key
        plain = decrypt_api_key(secret)
    except Exception:
        plain = secret
    if len(plain) <= 4:
        return "****"
    return plain[:4] + "****"


def _channel_to_response(channel: NotificationChannel) -> NotificationChannelResponse:
    """渠道模型转响应（含脱敏字段）"""
    return NotificationChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        webhook_url=_mask_webhook(channel.webhook_url),
        sign_enabled=channel.sign_enabled,
        enabled=channel.enabled,
        description=channel.description,
        created_by=channel.created_by,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        secret_masked=_mask_secret(channel.secret),
        has_secret=bool(channel.secret),
    )


# ==================== 事件类型 ====================

@router.get("/events", response_model=List[EventTypeInfo])
def list_notification_events(
    current_user: User = Depends(get_current_user),
):
    """获取支持的通知事件类型列表（供下拉选择）"""
    return [EventTypeInfo(**e) for e in EVENT_TYPES]


# ==================== 通知渠道 ====================

@router.get("/channels", response_model=List[NotificationChannelResponse])
def list_channels(
    keyword: Optional[str] = Query(None, description="按名称搜索"),
    channel_type: Optional[str] = Query(None, description="按类型筛选"),
    enabled: Optional[bool] = Query(None, description="按启用状态筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知渠道列表"""
    query = db.query(NotificationChannel)
    if keyword:
        query = query.filter(NotificationChannel.name.like(f"%{keyword}%"))
    if channel_type:
        query = query.filter(NotificationChannel.channel_type == channel_type)
    if enabled is not None:
        query = query.filter(NotificationChannel.enabled == enabled)
    channels = query.order_by(NotificationChannel.id.desc()).all()
    return [_channel_to_response(c) for c in channels]


@router.post("/channels", response_model=NotificationChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    data: NotificationChannelCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建通知渠道"""
    from app.agents.llm_factory import encrypt_api_key

    # 验签开启时必须提供密钥
    if data.sign_enabled and not data.secret:
        raise HTTPException(status_code=400, detail="启用签名校验时必须填写签名密钥")

    channel = NotificationChannel(
        name=data.name,
        channel_type=data.channel_type,
        webhook_url=data.webhook_url,
        secret=encrypt_api_key(data.secret) if data.secret else None,
        sign_enabled=data.sign_enabled,
        enabled=data.enabled,
        description=data.description,
        created_by=current_user.id,
    )
    db.add(channel)
    db.flush()

    log_audit(
        db, action="create", resource_type="notification_channel",
        resource_id=channel.id, resource_name=channel.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": channel.name, "channel_type": channel.channel_type},
    )
    db.commit()
    db.refresh(channel)
    return _channel_to_response(channel)


@router.put("/channels/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    channel_id: int,
    data: NotificationChannelUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新通知渠道"""
    from app.agents.llm_factory import encrypt_api_key

    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="通知渠道不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 密钥处理：传了新密钥才加密更新；传空字符串则清除密钥
    if "secret" in update_data:
        new_secret = update_data.pop("secret")
        if new_secret:
            update_data["secret"] = encrypt_api_key(new_secret)
        else:
            update_data["secret"] = None
            update_data["sign_enabled"] = False

    # 验签开启校验
    new_sign_enabled = update_data.get("sign_enabled", channel.sign_enabled)
    if new_sign_enabled and not update_data.get("secret", channel.secret):
        raise HTTPException(status_code=400, detail="启用签名校验时必须填写签名密钥")

    for key, value in update_data.items():
        setattr(channel, key, value)

    log_audit(
        db, action="update", resource_type="notification_channel",
        resource_id=channel.id, resource_name=channel.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": channel.name},
    )
    db.commit()
    db.refresh(channel)
    return _channel_to_response(channel)


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除通知渠道（软删除）"""
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="通知渠道不存在")

    # 检查是否有关联规则
    rule_count = db.query(NotificationRule).filter(
        NotificationRule.channel_id == channel_id,
        NotificationRule.enabled == True,
    ).count()
    if rule_count > 0:
        raise HTTPException(status_code=400, detail=f"该渠道下有 {rule_count} 条启用的规则，请先处理或禁用规则")

    channel.soft_delete()
    log_audit(
        db, action="delete", resource_type="notification_channel",
        resource_id=channel.id, resource_name=channel.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": channel.name},
    )
    db.commit()


@router.post("/channels/{channel_id}/test", response_model=TestSendResult)
def test_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送测试消息验证渠道配置"""
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="通知渠道不存在")

    service = NotificationService(db)
    result = service.send_test_message(channel)

    return TestSendResult(
        success=result.get("success", False),
        status_code=result.get("status_code"),
        message="测试消息发送成功" if result.get("success") else (result.get("error") or "发送失败"),
        response=result.get("response"),
    )


# ==================== 通知规则 ====================

@router.get("/rules", response_model=PaginatedResponse)
def list_rules(
    event_code: Optional[str] = Query(None, description="按事件编码筛选"),
    channel_id: Optional[int] = Query(None, description="按渠道筛选"),
    enabled: Optional[bool] = Query(None, description="按启用状态筛选"),
    keyword: Optional[str] = Query(None, description="按规则名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知规则列表"""
    query = db.query(NotificationRule)
    if event_code:
        query = query.filter(NotificationRule.event_code == event_code)
    if channel_id:
        query = query.filter(NotificationRule.channel_id == channel_id)
    if enabled is not None:
        query = query.filter(NotificationRule.enabled == enabled)
    if keyword:
        query = query.filter(NotificationRule.name.like(f"%{keyword}%"))

    total = query.count()
    rules = query.order_by(NotificationRule.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for rule in rules:
        channel = db.query(NotificationChannel).filter(
            NotificationChannel.id == rule.channel_id
        ).first()
        resp = NotificationRuleResponse.model_validate(rule)
        resp.channel_name = channel.name if channel else None
        items.append(resp)

    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("/rules", response_model=NotificationRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    data: NotificationRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建通知规则"""
    # 校验渠道存在
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == data.channel_id).first()
    if not channel:
        raise HTTPException(status_code=400, detail="所选通知渠道不存在")

    # 校验事件编码合法
    valid_codes = {e["code"] for e in EVENT_TYPES}
    if data.event_code not in valid_codes:
        raise HTTPException(status_code=400, detail=f"不支持的事件编码: {data.event_code}")

    rule = NotificationRule(
        name=data.name,
        event_code=data.event_code,
        channel_id=data.channel_id,
        conditions=data.conditions or {},
        receivers=data.receivers or {},
        enabled=data.enabled,
        created_by=current_user.id,
    )
    db.add(rule)
    db.flush()

    log_audit(
        db, action="create", resource_type="notification_rule",
        resource_id=rule.id, resource_name=rule.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": rule.name, "event_code": rule.event_code, "channel_id": rule.channel_id},
    )
    db.commit()
    db.refresh(rule)

    resp = NotificationRuleResponse.model_validate(rule)
    resp.channel_name = channel.name
    return resp


@router.put("/rules/{rule_id}", response_model=NotificationRuleResponse)
def update_rule(
    rule_id: int,
    data: NotificationRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新通知规则"""
    rule = db.query(NotificationRule).filter(NotificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="通知规则不存在")

    update_data = data.model_dump(exclude_unset=True)

    if "channel_id" in update_data:
        channel = db.query(NotificationChannel).filter(
            NotificationChannel.id == update_data["channel_id"]
        ).first()
        if not channel:
            raise HTTPException(status_code=400, detail="所选通知渠道不存在")

    if "event_code" in update_data:
        valid_codes = {e["code"] for e in EVENT_TYPES}
        if update_data["event_code"] not in valid_codes:
            raise HTTPException(status_code=400, detail=f"不支持的事件编码: {update_data['event_code']}")

    for key, value in update_data.items():
        setattr(rule, key, value)

    log_audit(
        db, action="update", resource_type="notification_rule",
        resource_id=rule.id, resource_name=rule.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": rule.name, "event_code": rule.event_code},
    )
    db.commit()
    db.refresh(rule)

    channel = db.query(NotificationChannel).filter(NotificationChannel.id == rule.channel_id).first()
    resp = NotificationRuleResponse.model_validate(rule)
    resp.channel_name = channel.name if channel else None
    return resp


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除通知规则（软删除）"""
    rule = db.query(NotificationRule).filter(NotificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="通知规则不存在")

    rule.soft_delete()
    log_audit(
        db, action="delete", resource_type="notification_rule",
        resource_id=rule.id, resource_name=rule.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": rule.name, "event_code": rule.event_code},
    )
    db.commit()


# ==================== 通知记录 ====================

@router.get("/records", response_model=PaginatedResponse)
def list_records(
    project_id: Optional[int] = Query(None, description="按来源项目筛选"),
    event_code: Optional[str] = Query(None, description="按事件编码筛选"),
    status_filter: Optional[str] = Query(None, alias="status", description="按发送状态筛选"),
    channel_id: Optional[int] = Query(None, description="按渠道筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知记录列表（分页+筛选）"""
    query = db.query(NotificationRecord)
    if project_id:
        query = query.filter(NotificationRecord.project_id == project_id)
    if event_code:
        query = query.filter(NotificationRecord.event_code == event_code)
    if status_filter:
        query = query.filter(NotificationRecord.status == status_filter)
    if channel_id:
        query = query.filter(NotificationRecord.channel_id == channel_id)
    if start_date:
        query = query.filter(NotificationRecord.created_at >= start_date)
    if end_date:
        query = query.filter(NotificationRecord.created_at <= end_date + " 23:59:59")

    total = query.count()
    records = query.order_by(NotificationRecord.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 预加载渠道名称映射
    channel_ids = {r.channel_id for r in records if r.channel_id}
    channel_map = {}
    if channel_ids:
        channels = db.query(NotificationChannel).filter(NotificationChannel.id.in_(channel_ids)).all()
        channel_map = {c.id: c.name for c in channels}

    items = []
    for r in records:
        resp = NotificationRecordResponse.model_validate(r)
        resp.channel_name = channel_map.get(r.channel_id)
        resp.event_name = get_event_name(r.event_code)
        # 计算耗时
        if r.sent_at and r.created_at:
            resp.duration_ms = int((r.sent_at - r.created_at).total_seconds() * 1000)
        items.append(resp)

    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/records/{record_id}", response_model=NotificationRecordResponse)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知记录详情"""
    record = db.query(NotificationRecord).filter(NotificationRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="通知记录不存在")

    resp = NotificationRecordResponse.model_validate(record)
    if record.channel_id:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == record.channel_id).first()
        resp.channel_name = channel.name if channel else None
    resp.event_name = get_event_name(record.event_code)
    if record.sent_at and record.created_at:
        resp.duration_ms = int((record.sent_at - record.created_at).total_seconds() * 1000)
    return resp


@router.post("/records/{record_id}/retry", response_model=NotificationRecordResponse)
def retry_record(
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重试发送失败的通知"""
    record = db.query(NotificationRecord).filter(NotificationRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="通知记录不存在")
    if record.status == "success":
        raise HTTPException(status_code=400, detail="该通知已发送成功，无需重试")

    service = NotificationService(db)
    record = service.retry_record(record)

    log_audit(
        db, action="retry", resource_type="notification_record",
        resource_id=record.id, resource_name=record.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"event_code": record.event_code, "retry_count": record.retry_count},
    )
    db.commit()
    db.refresh(record)

    resp = NotificationRecordResponse.model_validate(record)
    if record.channel_id:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == record.channel_id).first()
        resp.channel_name = channel.name if channel else None
    resp.event_name = get_event_name(record.event_code)
    return resp

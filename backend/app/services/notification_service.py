"""
通知核心服务

职责：
- 维护事件类型元数据 EVENT_TYPES（供前端下拉）
- NotificationService.send_event：查询全局启用规则 → 构建卡片 → 创建发送记录 → 异步派发
- 模块级便捷函数 notify_event：供业务模块一行调用，自带 session 与异常隔离，不阻塞主流程

规则条件匹配（rule.conditions JSON）：
- project_ids: [1,2]  仅当事件来源项目在列表中时触发（为空/不存在表示全部项目）
- min_failures: 1     失败数 >= 阈值才通知（用于 plan/scenario/suite）
- only_on_failure: true 仅失败时通知
- severities: ["致命","严重"] 缺陷严重程度筛选
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.tasks import dispatch_task
from app.core.timezone import china_now_naive
from app.database import SessionLocal
from app.models.notification import NotificationChannel, NotificationRecord, NotificationRule
from app.models.user import User
from app.services.card_builder import CardBuilder

logger = logging.getLogger(__name__)


def _parse_rule_event_codes(raw) -> list:
    """从规则的 event_code 字段解析事件编码列表（兼容旧数据）"""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [raw]
    return []


# ==================== 事件类型元数据 ====================

EVENT_TYPES: List[Dict[str, str]] = [
    # 测试执行类
    {"code": "plan.execution.completed", "name": "测试计划执行完成", "category": "测试执行", "level": "success", "color": "green", "description": "测试计划全部节点执行通过"},
    {"code": "plan.execution.failed", "name": "测试计划执行有失败", "category": "测试执行", "level": "warning", "color": "orange", "description": "测试计划执行存在失败节点"},
    {"code": "api.scenario.completed", "name": "接口场景执行完成", "category": "测试执行", "level": "info", "color": "blue", "description": "接口场景编排执行结束"},
    {"code": "ui.suite.completed", "name": "UI自动化编排完成", "category": "测试执行", "level": "info", "color": "blue", "description": "UI自动化套件执行结束"},
    {"code": "ui.script.failed", "name": "UI脚本执行失败", "category": "测试执行", "level": "warning", "color": "orange", "description": "单个UI自动化脚本执行失败"},
    {"code": "performance.completed", "name": "性能测试完成", "category": "测试执行", "level": "info", "color": "blue", "description": "性能测试执行结束"},
    # AI任务类
    {"code": "ai.requirement.generated", "name": "AI需求生成完成", "category": "AI任务", "level": "info", "color": "blue", "description": "AI异步生成需求文档结束"},
    {"code": "requirement.features_split", "name": "需求功能点拆分完成", "category": "AI任务", "level": "success", "color": "green", "description": "需求自动拆分为模块和功能点"},
    {"code": "ai.case.generated", "name": "AI功能用例生成完成", "category": "AI任务", "level": "info", "color": "blue", "description": "功能用例AI批量生成结束"},
    {"code": "ai.api_case.generated", "name": "AI接口用例生成完成", "category": "AI任务", "level": "info", "color": "blue", "description": "接口用例AI生成结束"},
    {"code": "ai.api_doc.generated", "name": "AI接口文档生成完成", "category": "AI任务", "level": "info", "color": "blue", "description": "接口文档AI生成结束"},
    {"code": "ai.report.generated", "name": "AI测试报告生成完成", "category": "AI任务", "level": "info", "color": "blue", "description": "AI版本测试报告生成结束"},
    {"code": "ai.task.failed", "name": "AI任务执行失败", "category": "AI任务", "level": "error", "color": "red", "description": "任意Agent异步任务执行失败"},
    # 缺陷协作类
    {"code": "defect.created", "name": "新缺陷创建", "category": "缺陷协作", "level": "warning", "color": "red", "description": "手动创建或自动创建缺陷"},
    {"code": "defect.assigned", "name": "缺陷分配", "category": "缺陷协作", "level": "info", "color": "blue", "description": "缺陷负责人变更"},
    {"code": "defect.resolved", "name": "缺陷已解决", "category": "缺陷协作", "level": "success", "color": "green", "description": "缺陷状态变更为已解决"},
    {"code": "defect.closed", "name": "缺陷已关闭", "category": "缺陷协作", "level": "info", "color": "blue", "description": "缺陷状态变更为已关闭"},
    {"code": "defect.reopened", "name": "缺陷重新打开", "category": "缺陷协作", "level": "warning", "color": "orange", "description": "缺陷状态变更为重新打开"},
    # 数据处理类
    {"code": "knowledge.doc_processed", "name": "知识库文档解析完成", "category": "数据处理", "level": "info", "color": "blue", "description": "文档向量化处理结束"},
    {"code": "api.import.completed", "name": "接口批量导入完成", "category": "数据处理", "level": "info", "color": "blue", "description": "Postman/Swagger等格式导入结束"},
]

EVENT_TYPE_MAP = {e["code"]: e for e in EVENT_TYPES}


def get_event_name(event_code: str) -> str:
    """根据事件编码获取事件名称"""
    return EVENT_TYPE_MAP.get(event_code, {}).get("name", event_code)


# ==================== 条件匹配 ====================

def _match_conditions(rule: NotificationRule, event_code: str, project_id: Optional[int], context: Dict[str, Any]) -> bool:
    """判断规则条件是否满足"""
    conditions = rule.conditions or {}
    if not isinstance(conditions, dict):
        return True

    # 项目过滤
    project_ids = conditions.get("project_ids")
    if project_ids and project_id is not None:
        try:
            if int(project_id) not in [int(p) for p in project_ids]:
                return False
        except (TypeError, ValueError):
            pass

    # 仅失败时通知
    if conditions.get("only_on_failure"):
        failed_count = context.get("failed_count", 0) or 0
        success = context.get("success", True)
        if failed_count == 0 and success:
            return False

    # 失败数阈值
    min_failures = conditions.get("min_failures")
    if min_failures is not None:
        failed_count = context.get("failed_count", 0) or 0
        try:
            if int(failed_count) < int(min_failures):
                return False
        except (TypeError, ValueError):
            pass

    # 缺陷严重程度筛选
    severities = conditions.get("severities")
    if severities and event_code.startswith("defect."):
        sev = context.get("severity")
        if sev and sev not in severities:
            return False

    return True


# ==================== 通知服务 ====================

class NotificationService:
    """通知发送核心服务"""

    def __init__(self, db):
        self.db = db

    def _get_triggered_by_name(self, triggered_by: Optional[int]) -> Optional[str]:
        """将用户ID解析为用户名"""
        if not triggered_by:
            return None
        try:
            user = self.db.query(User).filter(User.id == triggered_by).first()
            if user:
                return getattr(user, "username", None) or getattr(user, "name", None) or str(triggered_by)
        except Exception:
            pass
        return str(triggered_by)

    def send_event(
        self,
        project_id: Optional[int],
        event_code: str,
        context: Optional[Dict[str, Any]] = None,
        triggered_by: Optional[int] = None,
    ) -> List[NotificationRecord]:
        """
        发送事件通知

        查询全局启用的规则+渠道，构建卡片，创建 pending 记录，异步派发发送。

        Returns:
            创建的通知记录列表
        """
        context = context or {}
        records: List[NotificationRecord] = []

        # 查询全局启用的规则（event_code 支持多选，存储为 JSON 字符串，需在 Python 中匹配）
        all_rules = (
            self.db.query(NotificationRule)
            .filter(NotificationRule.enabled == True)
            .all()
        )
        rules = []
        for r in all_rules:
            codes = _parse_rule_event_codes(r.event_code)
            if event_code in codes:
                rules.append(r)

        if not rules:
            return records

        # 解析触发人名称
        triggered_by_name = context.get("triggered_by_name") or self._get_triggered_by_name(triggered_by)

        # 确保 context 中有 project_id（卡片链接需要）
        if project_id is not None:
            context.setdefault("project_id", project_id)

        # 触发时间
        trigger_time = china_now_naive().strftime("%Y-%m-%d %H:%M")
        context.setdefault("trigger_time", trigger_time)

        sent_channel_ids = set()
        for rule in rules:
            # 条件匹配
            if not _match_conditions(rule, event_code, project_id, context):
                continue

            # 查询渠道
            channel = self.db.query(NotificationChannel).filter(
                NotificationChannel.id == rule.channel_id,
                NotificationChannel.enabled == True,
            ).first()
            if not channel:
                continue

            # 同一事件同一渠道只发一次（防止多规则重复）
            if channel.id in sent_channel_ids:
                continue
            sent_channel_ids.add(channel.id)

            # 构建卡片
            card = CardBuilder.build(event_code, context, triggered_by_name)
            card_json = json.dumps(card, ensure_ascii=False)

            # 从卡片 header 提取标题
            title = card.get("header", {}).get("title", {}).get("content", event_code)

            # 创建发送记录
            record = NotificationRecord(
                project_id=project_id,
                channel_id=channel.id,
                rule_id=rule.id,
                event_code=event_code,
                title=title,
                content=card_json,
                status="pending",
                retry_count=0,
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            records.append(record)

            # 异步派发发送
            self._dispatch_send(record.id)

        if records:
            logger.info(f"事件 {event_code} 已创建 {len(records)} 条通知记录")
        return records

    def _dispatch_send(self, record_id: int):
        """派发异步发送任务（Celery 优先，失败降级线程）"""
        try:
            from app.tasks.notification_tasks import send_notification_task
            dispatch_task(send_notification_task, record_id)
        except Exception as e:
            logger.warning(f"派发通知任务失败，降级为同步发送: {e}")
            # 兜底：直接同步发送
            try:
                from app.tasks.notification_tasks import _send_notification_sync
                _send_notification_sync(record_id)
            except Exception as e2:
                logger.exception(f"同步发送通知也失败: {e2}")

    def send_test_message(self, channel: NotificationChannel) -> Dict[str, Any]:
        """发送测试消息（同步，立即返回结果）"""
        from app.agents.llm_factory import decrypt_api_key
        from app.services.feishu_bot import FeishuBotClient

        secret = decrypt_api_key(channel.secret) if channel.secret else None
        client = FeishuBotClient(
            webhook_url=channel.webhook_url,
            secret=secret,
            sign_enabled=channel.sign_enabled,
        )
        text = (
            f"✅ AITS 通知测试消息\n\n"
            f"渠道名称：{channel.name}\n"
            f"渠道类型：{channel.channel_type}\n"
            f"发送时间：{china_now_naive().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"如果您收到此消息，说明机器人配置正确。"
        )
        return client.send_text(text)

    def retry_record(self, record: NotificationRecord) -> NotificationRecord:
        """重试发送失败的记录"""
        record.status = "pending"
        record.error_message = None
        record.response_code = None
        record.response_body = None
        self.db.commit()
        self.db.refresh(record)
        self._dispatch_send(record.id)
        return record


# ==================== 模块级便捷函数（业务集成入口） ====================

def notify_event(
    project_id: Optional[int],
    event_code: str,
    context: Optional[Dict[str, Any]] = None,
    triggered_by: Optional[int] = None,
):
    """
    业务模块发送通知的便捷入口。

    - 自带独立数据库 session
    - 全程异常隔离，通知失败不影响业务主流程
    - 异步发送，不阻塞调用方

    用法:
        from app.services.notification_service import notify_event
        notify_event(project_id, "plan.execution.completed", {...}, triggered_by=user_id)
    """
    try:
        db = SessionLocal()
        try:
            service = NotificationService(db)
            service.send_event(project_id, event_code, context, triggered_by)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"发送通知失败（已忽略，不影响业务）: event={event_code}, error={e}")


def notify_ai_task_failed(
    project_id: Optional[int],
    task_type: str,
    error: str,
    related_object: str = "-",
    triggered_by: Optional[int] = None,
):
    """
    AI 任务失败统一通知辅助函数。

    各 task 的 except 分支统一调用此函数发送 ai.task.failed 事件。
    """
    notify_event(
        project_id,
        "ai.task.failed",
        {
            "task_type": task_type,
            "error": error,
            "related_object": related_object,
        },
        triggered_by=triggered_by,
    )

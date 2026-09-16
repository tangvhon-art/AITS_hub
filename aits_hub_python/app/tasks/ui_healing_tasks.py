"""
UI 自愈聚合任务 — 将原始访问记录聚合为页面画像和元素指纹

聚合逻辑已抽取至 app.services.ui_healing.knowledge_aggregator
本模块仅提供 Celery 任务入口
"""
import logging

from app.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ui_healing_tasks.aggregate_page_knowledge")
def aggregate_page_knowledge(project_id: int = None, batch_size: int = 500):
    """
    聚合页面知识（定时任务 / 自动触发）

    1. 按 page_identifier 分组统计原始记录
    2. SQL 计算访问次数、成功率
    3. 提取元素指纹
    4. AI 生成页面名称和描述
    """
    db = SessionLocal()
    try:
        from app.services.ui_healing.knowledge_aggregator import aggregate_page_knowledge_sync
        return aggregate_page_knowledge_sync(db, project_id=project_id, batch_size=batch_size)
    except Exception as e:
        logger.error(f"页面知识聚合任务失败: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()

"""
清理任务 — 定期清理上传文件（执行截图、自愈截图等）与调度执行日志

提供两种调用方式：
1. 执行前调用 cleanup_uploads() 清理旧截图
2. Celery 定时任务每 3 小时自动清理

调度日志清理任务 cleanup_celery_beat_logs 支持在任务调度页面可视化配置
kwargs 动态传参：{"clean_unit": "hour/day/month", "clean_value": 正整数}
"""
import os
import shutil
import logging
import time
from datetime import timedelta

from app.celery_app import celery_app
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


def get_uploads_dir() -> str:
    """获取 uploads 目录路径（与 main.py 静态文件服务一致）"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "uploads",
    )


def cleanup_uploads() -> int:
    """
    清理 uploads 目录下的所有文件和子目录

    删除 execution/ 和 healing/ 等子目录下的全部文件，
    保留 uploads 根目录本身（避免影响静态文件服务挂载）。

    Returns:
        删除的文件数量
    """
    uploads_dir = get_uploads_dir()
    if not os.path.exists(uploads_dir):
        return 0

    count = 0
    for item in os.listdir(uploads_dir):
        item_path = os.path.join(uploads_dir, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
                count += 1
            elif os.path.isdir(item_path):
                for _root, _dirs, files in os.walk(item_path):
                    count += len(files)
                shutil.rmtree(item_path)
        except Exception as e:
            logger.debug(f"清理失败: {item_path}: {e}")

    logger.info(f"uploads 清理完成，共删除 {count} 个文件")
    return count


@celery_app.task(name="app.tasks.cleanup_tasks.cleanup_uploads_task")
def cleanup_uploads_task():
    """Celery 定时任务：清理 uploads 目录"""
    deleted = cleanup_uploads()
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# 调度执行日志清理（sys_celery_task_log）
# ---------------------------------------------------------------------------

_VALID_CLEAN_UNITS = ("hour", "day", "month")
# 软删日志保留天数：软删超过该天数的记录才物理清除
_SOFT_DELETED_RETENTION_DAYS = 30


def _calc_cutoff(clean_unit: str, clean_value: int):
    """按 unit + value 计算清理截止时间（该时间之前的日志将被清理）"""
    now = china_now_naive()
    if clean_unit == "hour":
        return now - timedelta(hours=clean_value)
    if clean_unit == "day":
        return now - timedelta(days=clean_value)
    # month：按自然月回退，日序越界时收敛到目标月最后一天
    month_index = now.month - 1 - clean_value
    year = now.year + month_index // 12
    month = month_index % 12 + 1
    for day in (now.day, 30, 29, 28):
        try:
            return now.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    raise ValueError(f"无法计算 {clean_value} 个月前的截止时间")


@celery_app.task(name="app.tasks.cleanup_tasks.cleanup_celery_beat_logs")
def cleanup_celery_beat_logs(clean_unit: str = None, clean_value: int = None):
    """
    Celery 定时任务：清理调度执行日志（sys_celery_task_log）

    kwargs 动态参数（前端任务调度页面可视化配置）：
    - clean_unit：时间单位，可选 hour / day / month
    - clean_value：正整数
    示例：{"clean_unit": "day", "clean_value": 7} 清理7天前日志
    无参数时默认清理 1 个月前日志。

    遵循项目软删约束：先软删截止时间前的日志，再物理清除
    软删超过保留期（30天）的记录（已无任何查询入口的历史数据）。
    参数非法时直接报错，任务以 FAILURE 退出（执行日志页可见异常信息）。
    """
    start = time.time()

    # 无参兜底：默认清理 1 个月前日志
    if clean_unit is None and clean_value is None:
        clean_unit, clean_value = "month", 1
        logger.info("未传入清理参数，使用默认策略：清理 1 个月前的调度日志")

    # 参数合法性校验（非法直接抛出，任务失败退出）
    if clean_unit not in _VALID_CLEAN_UNITS:
        raise ValueError(
            f"clean_unit 非法: {clean_unit!r}，仅支持 {'/'.join(_VALID_CLEAN_UNITS)}"
        )
    if not isinstance(clean_value, int) or isinstance(clean_value, bool) or clean_value <= 0:
        raise ValueError(f"clean_value 必须为正整数，当前值: {clean_value!r}")

    from app.database import SessionLocal
    from app.models.celery_task_log import CeleryTaskLog

    cutoff = _calc_cutoff(clean_unit, clean_value)
    db = SessionLocal()
    try:
        # 阶段1：软删截止时间之前的日志
        soft_deleted = db.query(CeleryTaskLog).filter(
            CeleryTaskLog.is_deleted == False,  # noqa: E712
            CeleryTaskLog.created_at < cutoff,
        ).update(
            {"is_deleted": True, "deleted_at": china_now_naive()},
            synchronize_session=False,
        )
        # 阶段2：物理清除软删超过保留期的记录
        purge_before = china_now_naive() - timedelta(days=_SOFT_DELETED_RETENTION_DAYS)
        purged = db.query(CeleryTaskLog).filter(
            CeleryTaskLog.is_deleted == True,  # noqa: E712
            CeleryTaskLog.deleted_at < purge_before,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        f"调度日志清理完成：软删 {soft_deleted} 条（创建时间早于 {cutoff:%Y-%m-%d %H:%M:%S}，"
        f"即 {clean_value} {clean_unit} 前），物理清除历史软删 {purged} 条，耗时 {elapsed_ms}ms"
    )
    return {
        "soft_deleted": soft_deleted,
        "purged": purged,
        "cutoff": cutoff.strftime("%Y-%m-%d %H:%M:%S"),
        "clean_unit": clean_unit,
        "clean_value": clean_value,
        "elapsed_ms": elapsed_ms,
    }


@celery_app.task(name="app.tasks.cleanup_tasks.cleanup_workflow_call_logs")
def cleanup_workflow_call_logs(clean_unit: str = None, clean_value: int = None):
    """
    Celery 定时任务：清理外部工作流调用日志（workflow_call_log）

    kwargs 动态参数（前端任务调度页面可视化配置）：
    - clean_unit：时间单位，可选 hour / day / month
    - clean_value：正整数
    示例：{"clean_unit": "day", "clean_value": 30} 清理30天前日志
    无参数时默认清理 30 天前日志。

    调用日志包含 invoke/accept/callback/complete/fail 等阶段，
    长期运行会导致表膨胀，建议定期清理。
    """
    start = time.time()

    # 无参兜底：默认清理 30 天前日志
    if clean_unit is None and clean_value is None:
        clean_unit, clean_value = "day", 30
        logger.info("未传入清理参数，使用默认策略：清理 30 天前的工作流调用日志")

    # 参数合法性校验
    if clean_unit not in _VALID_CLEAN_UNITS:
        raise ValueError(
            f"clean_unit 非法: {clean_unit!r}，仅支持 {'/'.join(_VALID_CLEAN_UNITS)}"
        )
    if not isinstance(clean_value, int) or isinstance(clean_value, bool) or clean_value <= 0:
        raise ValueError(f"clean_value 必须为正整数，当前值: {clean_value!r}")

    from app.database import SessionLocal
    from app.models.workflow import WorkflowCallLog

    cutoff = _calc_cutoff(clean_unit, clean_value)
    db = SessionLocal()
    try:
        # 物理删除截止时间之前的日志（调用日志无软删需求）
        deleted = db.query(WorkflowCallLog).filter(
            WorkflowCallLog.created_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        f"工作流调用日志清理完成：删除 {deleted} 条（创建时间早于 {cutoff:%Y-%m-%d %H:%M:%S}，"
        f"即 {clean_value} {clean_unit} 前），耗时 {elapsed_ms}ms"
    )
    return {
        "deleted": deleted,
        "cutoff": cutoff.strftime("%Y-%m-%d %H:%M:%S"),
        "clean_unit": clean_unit,
        "clean_value": clean_value,
        "elapsed_ms": elapsed_ms,
    }

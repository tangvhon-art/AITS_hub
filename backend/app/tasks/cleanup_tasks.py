"""
清理任务 — 定期清理上传文件（执行截图、自愈截图等）

提供两种调用方式：
1. 执行前调用 cleanup_uploads() 清理旧截图
2. Celery 定时任务每 3 小时自动清理
"""
import os
import shutil
import logging

from app.celery_app import celery_app

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

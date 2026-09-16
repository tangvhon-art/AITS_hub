"""
数据库驱动的 Celery Beat 调度器（动态定时任务）

- Beat 进程每隔 DB_POLL_INTERVAL 秒轮询 sys_crontab 表，
  检测到变更（新增/修改/删除/启停）后自动重建调度计划，无需重启 beat
- 支持两种调度类型：interval（间隔秒数）/ cron（cron 表达式）
- 每个任务按自身 queue 字段路由到 default/ai/execution 队列
- 任务每次投递后回写 last_run_at / total_run_count 执行统计

⚠️ Beat 必须单实例运行：多个 beat 进程会重复调度、重复派发任务！
   启动时务必使用 --pidfile 并确保旧 beat 已停止（start.sh 已处理）。
"""
import logging
from datetime import datetime, timedelta

from celery import current_app
from celery.beat import Scheduler, ScheduleEntry
from celery.schedules import crontab as celery_crontab
from celery.schedules import schedule as celery_interval

from app.core.timezone import CHINA_TZ, china_now, china_now_naive
from app.database import SessionLocal
from app.models.sys_crontab import SysCrontab

logger = logging.getLogger(__name__)

# sys_crontab 轮询间隔（秒）：任务变更最长在该时间后生效
DB_POLL_INTERVAL = 5.0


def _to_aware_beijing(dt):
    """DB 存储的是 naive 北京时间，补上时区转为 aware。

    celery schedule 内部的 now() 是 aware(+08:00)，若 last_run_at 为 naive
    会被当作 UTC 参与减法，导致到期时间偏移 8 小时。
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=CHINA_TZ)


class DatabaseScheduleEntry(ScheduleEntry):
    """将 sys_crontab 一行记录转换为 beat 可调度的 ScheduleEntry"""

    def __init__(self, model, app=None):
        self.model_id = model.id
        self.app = app or current_app._get_current_object()
        self.name = f"sys_crontab_{model.id}"
        self.task = model.task
        self.args = model.args or []
        self.kwargs = model.kwargs or {}
        self.options = {"queue": model.queue or "default"}
        self.total_run_count = model.total_run_count or 0
        # 从未执行过的任务以最近更新时间为基准，避免 beat 启动后立即补跑
        last_run = model.last_run_at or model.updated_at
        self.last_run_at = _to_aware_beijing(last_run) or china_now()
        if model.schedule_type == "cron":
            self.schedule = celery_crontab(
                minute=model.minute or "*",
                hour=model.hour or "*",
                day_of_week=model.day_of_week or "*",
                day_of_month=model.day_of_month or "*",
                month_of_year=model.month_of_year or "*",
            )
        else:
            self.schedule = celery_interval(
                timedelta(seconds=model.every_seconds or 60)
            )


class DatabaseScheduler(Scheduler):
    """从 sys_crontab 表动态加载调度计划的自定义 Beat Scheduler"""

    Entry = DatabaseScheduleEntry

    def __init__(self, *args, **kwargs):
        self._schedule = {}
        self._last_signature = None
        self._last_poll = None
        super().__init__(*args, **kwargs)

    # ---------- 初始化 ----------

    def setup_schedule(self):
        self._sync_from_db(force=True)
        logger.info(
            f"DatabaseScheduler 初始化完成，加载 {len(self._schedule)} 个定时任务"
        )

    @property
    def schedule(self):
        return self._schedule

    @schedule.setter
    def schedule(self, value):
        self._schedule = value

    # ---------- 主循环：beat Service 按 tick() 返回值休眠后再调用，
    # 必须将返回值限制在 DB_POLL_INTERVAL 内，否则任务间隔长时
    # beat 会长时间休眠，无法及时感知 sys_crontab 变更

    def tick(self):
        self._sync_from_db()
        return min(super().tick(), DB_POLL_INTERVAL)

    def _sync_from_db(self, force: bool = False):
        now = datetime.now()
        if (
            not force
            and self._last_poll is not None
            and (now - self._last_poll).total_seconds() < DB_POLL_INTERVAL
        ):
            return
        self._last_poll = now

        try:
            db = SessionLocal()
            try:
                rows = (
                    db.query(SysCrontab)
                    .filter(
                        SysCrontab.is_deleted == False,  # noqa: E712
                        SysCrontab.enabled == True,  # noqa: E712
                    )
                    .all()
                )
                # 变更签名：任务 id + 更新时间；执行统计回写不触发 updated_at 变更
                signature = tuple(sorted((r.id, r.updated_at) for r in rows))
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"DatabaseScheduler 读取 sys_crontab 失败（沿用当前计划）: {e}")
            return

        if not force and signature == self._last_signature:
            return

        new_schedule = {}
        for row in rows:
            try:
                new_schedule[f"sys_crontab_{row.id}"] = self.Entry(row, app=self.app)
            except Exception as e:
                logger.error(f"构建定时任务失败 sys_crontab id={row.id}: {e}")
        self._schedule = new_schedule
        self._last_signature = signature
        logger.info(
            f"DatabaseScheduler 检测到 sys_crontab 变更，已重载 {len(new_schedule)} 个任务"
        )

    # ---------- 任务投递与统计回写 ----------

    def apply_entry(self, entry, producer=None):
        try:
            self.send_task(
                entry.task, entry.args, entry.kwargs,
                producer=producer, **entry.options
            )
        except Exception as e:
            logger.error(f"定时任务派发失败 {entry.task}: {e}", exc_info=True)
            return
        # 回写执行统计（Query.update 不触发 updated_at onupdate，避免误判为配置变更）
        now = china_now()          # entry 内存中保持 aware 北京时间
        now_naive = china_now_naive()  # DB 中保持 naive 北京时间（与全库一致）
        entry.last_run_at = now
        entry.total_run_count += 1
        try:
            db = SessionLocal()
            try:
                db.query(SysCrontab).filter(SysCrontab.id == entry.model_id).update(
                    {
                        "last_run_at": now_naive,
                        "total_run_count": entry.total_run_count,
                    },
                    synchronize_session=False,
                )
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"回写 sys_crontab 执行统计失败: {e}")

    def reserve(self, entry):
        return entry

    def sync(self):
        pass

    def close(self):
        pass

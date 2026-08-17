"""Celery 任务模块

导入所有任务模块，确保 Celery app 在任意进程（worker / FastAPI / 脚本）
中均能注册全部任务，避免 NotRegistered 错误。
"""
from app.tasks.script_tasks import *  # noqa: F401,F403
from app.tasks.api_case_tasks import *  # noqa: F401,F403
from app.tasks.test_plan_tasks import *  # noqa: F401,F403
from app.tasks.performance_tasks import *  # noqa: F401,F403
from app.tasks.api_doc_tasks import *  # noqa: F401,F403
from app.tasks.case_tasks import *  # noqa: F401,F403
from app.tasks.notification_tasks import *  # noqa: F401,F403
from app.tasks.requirement_tasks import *  # noqa: F401,F403
from app.tasks.knowledge_tasks import *  # noqa: F401,F403
from app.tasks.report_tasks import *  # noqa: F401,F403
from app.tasks.review_tasks import *  # noqa: F401,F403

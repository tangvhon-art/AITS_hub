"""
缺陷自动创建工具
在执行失败时自动创建缺陷记录，打通执行→缺陷闭环
"""
import logging
from sqlalchemy.orm import Session

from app.models.defect import Defect
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


def auto_create_defect(
    db: Session,
    project_id: int,
    title: str,
    description: str,
    error_message: str = "",
    severity: str = "major",
    priority: str = "P2",
    source: str = "automation",
    case_id: int = None,
    run_id: int = None,
    version_id: int = None,
    created_by: int = None,
) -> Defect:
    """
    执行失败时自动创建缺陷记录

    Args:
        db: 数据库会话
        project_id: 项目ID
        title: 缺陷标题
        description: 缺陷描述
        error_message: 错误信息
        severity: 严重程度（blocker/critical/major/minor/trivial）
        priority: 优先级（P0/P1/P2/P3）
        source: 来源标记（automation/api_case/api_scenario/ui_script）
        case_id: 关联用例ID
        run_id: 关联执行记录ID
        version_id: 关联版本ID
        created_by: 创建人ID

    Returns:
        创建的 Defect 对象
    """
    try:
        defect = Defect(
            project_id=project_id,
            version_id=version_id,
            run_id=run_id,
            case_id=case_id,
            title=title,
            description=description,
            severity=severity,
            priority=priority,
            status="open",
            actual_result=error_message,
            error_log=error_message,
            root_cause_category="other",
            created_by=created_by,
        )
        db.add(defect)
        db.commit()
        db.refresh(defect)
        logger.info(f"自动创建缺陷: #{defect.id} - {title} (source={source})")
        return defect
    except Exception as e:
        logger.error(f"自动创建缺陷失败: {e}", exc_info=True)
        db.rollback()
        return None

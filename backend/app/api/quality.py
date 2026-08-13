"""
质量看板与洞察 API
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.defect import Defect
from app.models.test_plan import TestPlan
from app.schemas.test_plan import (
    QualityMetricsResponse, QualityTrendResponse, TrendDataPoint,
    DefectDistributionItem, QualityDashboardResponse, RiskAlertResponse, RiskAlertItem
)

router = APIRouter()
project_router = APIRouter(prefix="/api/projects/{project_id}")


def _calculate_metrics(project_id: int, db: Session) -> QualityMetricsResponse:
    """计算项目质量指标"""
    total_cases = db.query(func.count(TestCase.id)).filter(TestCase.project_id == project_id).scalar() or 0
    active_cases = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project_id,
        TestCase.status == "active"
    ).scalar() or 0

    total_runs = db.query(func.count(TestRun.id)).filter(TestRun.project_id == project_id).scalar() or 0
    passed_runs = db.query(func.count(TestRun.id)).filter(
        TestRun.project_id == project_id,
        TestRun.status == "passed"
    ).scalar() or 0
    failed_runs = db.query(func.count(TestRun.id)).filter(
        TestRun.project_id == project_id,
        TestRun.status == "failed"
    ).scalar() or 0

    pass_rate = round((passed_runs / total_runs * 100), 2) if total_runs > 0 else 0.0

    total_defects = db.query(func.count(Defect.id)).filter(Defect.project_id == project_id).scalar() or 0
    open_defects = db.query(func.count(Defect.id)).filter(
        Defect.project_id == project_id,
        Defect.status.in_(["open", "confirmed", "reopened"])
    ).scalar() or 0
    resolved_defects = db.query(func.count(Defect.id)).filter(
        Defect.project_id == project_id,
        Defect.status.in_(["resolved", "closed"])
    ).scalar() or 0

    defect_density = round((total_defects / total_cases), 2) if total_cases > 0 else 0.0

    avg_duration_result = db.query(func.avg(TestRun.duration)).filter(
        TestRun.project_id == project_id,
        TestRun.duration.isnot(None)
    ).scalar()
    avg_duration = round(float(avg_duration_result or 0), 2)

    total_plans = db.query(func.count(TestPlan.id)).filter(TestPlan.project_id == project_id).scalar() or 0
    completed_plans = db.query(func.count(TestPlan.id)).filter(
        TestPlan.project_id == project_id,
        TestPlan.status == "completed"
    ).scalar() or 0

    return QualityMetricsResponse(
        total_cases=total_cases,
        active_cases=active_cases,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        pass_rate=pass_rate,
        total_defects=total_defects,
        open_defects=open_defects,
        resolved_defects=resolved_defects,
        defect_density=defect_density,
        avg_duration=avg_duration,
        total_plans=total_plans,
        completed_plans=completed_plans
    )


def _calculate_trend(project_id: int, days: int, db: Session) -> QualityTrendResponse:
    """计算趋势数据"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # 通过率趋势（按天）
    pass_rate_trend = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        day_total = db.query(func.count(TestRun.id)).filter(
            TestRun.project_id == project_id,
            TestRun.completed_at >= day_start,
            TestRun.completed_at <= day_end
        ).scalar() or 0
        day_passed = db.query(func.count(TestRun.id)).filter(
            TestRun.project_id == project_id,
            TestRun.status == "passed",
            TestRun.completed_at >= day_start,
            TestRun.completed_at <= day_end
        ).scalar() or 0

        rate = round((day_passed / day_total * 100), 2) if day_total > 0 else 0.0
        pass_rate_trend.append(TrendDataPoint(date=day.strftime("%Y-%m-%d"), value=rate))

    # 缺陷趋势
    defect_trend = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        day_defects = db.query(func.count(Defect.id)).filter(
            Defect.project_id == project_id,
            Defect.created_at >= day_start,
            Defect.created_at <= day_end
        ).scalar() or 0
        defect_trend.append(TrendDataPoint(date=day.strftime("%Y-%m-%d"), value=float(day_defects)))

    # 执行次数趋势
    execution_trend = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        day_runs = db.query(func.count(TestRun.id)).filter(
            TestRun.project_id == project_id,
            TestRun.created_at >= day_start,
            TestRun.created_at <= day_end
        ).scalar() or 0
        execution_trend.append(TrendDataPoint(date=day.strftime("%Y-%m-%d"), value=float(day_runs)))

    return QualityTrendResponse(
        pass_rate_trend=pass_rate_trend,
        defect_trend=defect_trend,
        execution_trend=execution_trend
    )


def _calculate_defect_distribution(project_id: int, db: Session):
    """计算缺陷分布"""
    # 严重程度分布
    severity_data = db.query(
        Defect.severity,
        func.count(Defect.id)
    ).filter(Defect.project_id == project_id).group_by(Defect.severity).all()

    severity_distribution = [
        DefectDistributionItem(category=sev or "unknown", count=cnt)
        for sev, cnt in severity_data
    ]

    # 根因分类分布
    category_data = db.query(
        Defect.root_cause_category,
        func.count(Defect.id)
    ).filter(Defect.project_id == project_id).group_by(Defect.root_cause_category).all()

    category_distribution = [
        DefectDistributionItem(category=cat or "other", count=cnt)
        for cat, cnt in category_data
    ]

    return severity_distribution, category_distribution


def _calculate_module_pass_rate(project_id: int, db: Session) -> List[Dict[str, Any]]:
    """计算模块通过率"""
    modules = db.query(TestCase.module).filter(
        TestCase.project_id == project_id,
        TestCase.module.isnot(None)
    ).distinct().all()

    result = []
    for (module,) in modules:
        module_cases = db.query(func.count(TestCase.id)).filter(
            TestCase.project_id == project_id,
            TestCase.module == module
        ).scalar() or 0

        module_runs = db.query(func.count(TestRun.id)).filter(
            TestRun.project_id == project_id,
            TestRun.case_id.in_(
                db.query(TestCase.id).filter(TestCase.project_id == project_id, TestCase.module == module)
            )
        ).scalar() or 0

        module_passed = db.query(func.count(TestRun.id)).filter(
            TestRun.project_id == project_id,
            TestRun.status == "passed",
            TestRun.case_id.in_(
                db.query(TestCase.id).filter(TestCase.project_id == project_id, TestCase.module == module)
            )
        ).scalar() or 0

        rate = round((module_passed / module_runs * 100), 2) if module_runs > 0 else 0.0
        result.append({
            "module": module,
            "total_cases": module_cases,
            "total_runs": module_runs,
            "passed_runs": module_passed,
            "pass_rate": rate
        })

    return result


def _generate_risk_alerts(project_id: int, db: Session) -> RiskAlertResponse:
    """生成风险预警"""
    alerts = []
    metrics = _calculate_metrics(project_id, db)
    now = datetime.utcnow()

    # 通过率低于阈值
    if metrics.pass_rate < 70 and metrics.total_runs > 0:
        alerts.append(RiskAlertItem(
            id=f"pass_rate_{project_id}",
            level="high",
            title="通过率偏低",
            description=f"当前通过率为 {metrics.pass_rate}%，低于 70% 的质量门禁阈值",
            metric="pass_rate",
            current_value=metrics.pass_rate,
            threshold=70.0,
            created_at=now
        ))
    elif metrics.pass_rate < 85 and metrics.total_runs > 0:
        alerts.append(RiskAlertItem(
            id=f"pass_rate_{project_id}",
            level="medium",
            title="通过率需关注",
            description=f"当前通过率为 {metrics.pass_rate}%，建议关注质量趋势",
            metric="pass_rate",
            current_value=metrics.pass_rate,
            threshold=85.0,
            created_at=now
        ))

    # 未解决缺陷过多
    if metrics.open_defects > 10:
        alerts.append(RiskAlertItem(
            id=f"open_defects_{project_id}",
            level="high",
            title="未解决缺陷过多",
            description=f"当前有 {metrics.open_defects} 个未解决缺陷，建议优先处理",
            metric="open_defects",
            current_value=float(metrics.open_defects),
            threshold=10.0,
            created_at=now
        ))
    elif metrics.open_defects > 5:
        alerts.append(RiskAlertItem(
            id=f"open_defects_{project_id}",
            level="medium",
            title="未解决缺陷需关注",
            description=f"当前有 {metrics.open_defects} 个未解决缺陷",
            metric="open_defects",
            current_value=float(metrics.open_defects),
            threshold=5.0,
            created_at=now
        ))

    # 缺陷密度过高
    if metrics.defect_density > 0.5:
        alerts.append(RiskAlertItem(
            id=f"defect_density_{project_id}",
            level="high",
            title="缺陷密度过高",
            description=f"缺陷密度为 {metrics.defect_density}，高于 0.5 的警戒线",
            metric="defect_density",
            current_value=metrics.defect_density,
            threshold=0.5,
            created_at=now
        ))

    # 测试覆盖率不足
    if metrics.total_cases > 0 and metrics.active_cases / metrics.total_cases < 0.5:
        alerts.append(RiskAlertItem(
            id=f"coverage_{project_id}",
            level="medium",
            title="有效用例占比偏低",
            description=f"活跃用例占比为 {round(metrics.active_cases / metrics.total_cases * 100)}%，建议补充用例",
            metric="active_case_ratio",
            current_value=round(metrics.active_cases / metrics.total_cases * 100, 2),
            threshold=50.0,
            created_at=now
        ))

    # 模块级风险
    module_rates = _calculate_module_pass_rate(project_id, db)
    for mr in module_rates:
        if mr["pass_rate"] < 60 and mr["total_runs"] > 0:
            alerts.append(RiskAlertItem(
                id=f"module_{project_id}_{mr['module']}",
                level="high",
                title=f"模块「{mr['module']}」通过率偏低",
                description=f"模块通过率为 {mr['pass_rate']}%，存在质量风险",
                module=mr["module"],
                metric="module_pass_rate",
                current_value=mr["pass_rate"],
                threshold=60.0,
                created_at=now
            ))

    high = sum(1 for a in alerts if a.level == "high")
    medium = sum(1 for a in alerts if a.level == "medium")
    low = sum(1 for a in alerts if a.level == "low")

    return RiskAlertResponse(
        total=len(alerts),
        high=high,
        medium=medium,
        low=low,
        items=alerts
    )


@project_router.get("/quality/metrics", response_model=QualityMetricsResponse)
def get_quality_metrics(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取项目质量指标"""
    return _calculate_metrics(project_id, db)


@project_router.get("/quality/trend", response_model=QualityTrendResponse)
def get_quality_trend(
    project_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取质量趋势数据"""
    return _calculate_trend(project_id, days, db)


@project_router.get("/quality/dashboard", response_model=QualityDashboardResponse)
def get_quality_dashboard(
    project_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取完整质量看板数据"""
    metrics = _calculate_metrics(project_id, db)
    trend = _calculate_trend(project_id, days, db)
    severity_dist, category_dist = _calculate_defect_distribution(project_id, db)
    module_pass_rate = _calculate_module_pass_rate(project_id, db)

    return QualityDashboardResponse(
        metrics=metrics,
        trend=trend,
        severity_distribution=severity_dist,
        category_distribution=category_dist,
        module_pass_rate=module_pass_rate
    )


@project_router.get("/quality/alerts", response_model=RiskAlertResponse)
def get_risk_alerts(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取风险预警列表"""
    return _generate_risk_alerts(project_id, db)


@project_router.post("/quality/insight")
def generate_insight(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """生成质量洞察分析（基于规则，后续可接入 LLM）"""
    metrics = _calculate_metrics(project_id, db)
    alerts = _generate_risk_alerts(project_id, db)

    insights = []

    # 总体评价
    if metrics.pass_rate >= 90:
        insights.append("整体测试通过率良好，质量处于稳定状态。")
    elif metrics.pass_rate >= 70:
        insights.append("整体测试通过率一般，建议关注失败用例并分析根因。")
    else:
        insights.append("整体测试通过率偏低，存在较大质量风险，建议优先修复缺陷。")

    # 缺陷分析
    if metrics.open_defects > 0:
        insights.append(f"当前有 {metrics.open_defects} 个未解决缺陷，建议安排修复计划。")

    # 覆盖率建议
    if metrics.total_cases < 10:
        insights.append("测试用例数量较少，建议补充更多测试场景以提高覆盖率。")

    # 执行建议
    if metrics.total_runs == 0:
        insights.append("尚未有执行记录，建议尽快执行测试用例以验证质量。")

    return {
        "project_id": project_id,
        "insights": insights,
        "metrics": metrics,
        "alerts": alerts,
        "generated_at": datetime.utcnow().isoformat()
    }

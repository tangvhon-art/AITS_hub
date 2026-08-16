import fnmatch
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CoverageAnalyzer:
    """覆盖率分析器"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_api_coverage(
        self,
        project_id: int,
        version_id: Optional[int] = None,
        excluded_paths: List[str] = None,
        excluded_methods: List[str] = None,
    ) -> dict:
        """计算接口覆盖率"""
        from app.models.api_test import ApiDefinition, ApiTestCase, ApiScenarioStep

        excluded_paths = excluded_paths or []
        excluded_methods = [m.upper() for m in (excluded_methods or [])]

        query = self.db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id,
            ApiDefinition.is_deleted == False,
        )
        if version_id:
            query = query.filter(ApiDefinition.version_id == version_id)

        all_defs = query.all()

        filtered_defs = []
        for d in all_defs:
            if d.method and d.method.upper() in excluded_methods:
                continue
            if any(fnmatch.fnmatch(d.path or "", pattern) for pattern in excluded_paths):
                continue
            filtered_defs.append(d)

        cases = self.db.query(ApiTestCase).filter(
            ApiTestCase.project_id == project_id,
            ApiTestCase.is_deleted == False,
        ).all()

        scenario_steps = self.db.query(ApiScenarioStep).filter(
            ApiScenarioStep.is_deleted == False,
        ).all()

        covered_def_ids = set()
        coverage_matrix = {}

        for d in filtered_defs:
            case_ids = [c.id for c in cases if c.api_id == d.id]
            scenario_ids = [s.scenario_id for s in scenario_steps if s.api_id == d.id]
            is_covered = len(case_ids) > 0 or len(scenario_ids) > 0
            if is_covered:
                covered_def_ids.add(d.id)
            coverage_matrix[str(d.id)] = {
                "covered": is_covered,
                "case_ids": case_ids,
                "scenario_ids": list(set(scenario_ids)),
                "name": d.name,
                "method": d.method,
                "path": d.path,
            }

        total = len(filtered_defs)
        covered = len(covered_def_ids)
        rate = round(covered / total * 100, 2) if total > 0 else 0.0
        uncovered = [
            {"id": d.id, "name": d.name, "method": d.method, "path": d.path}
            for d in filtered_defs if d.id not in covered_def_ids
        ]

        return {
            "total_apis": total,
            "covered_apis": covered,
            "api_coverage_rate": rate,
            "uncovered_apis": uncovered,
            "coverage_matrix": coverage_matrix,
            "total_cases": len(cases),
            "cases_with_api": sum(1 for c in cases if c.api_id),
        }

    def calculate_scenario_coverage(self, project_id: int, critical_ids: List[int] = None) -> dict:
        """计算场景覆盖率"""
        from app.models.api_test import ApiScenario, ApiScenarioStep

        critical_ids = critical_ids or []
        if not critical_ids:
            return {
                "total_scenarios": 0,
                "covered_scenarios": 0,
                "scenario_coverage_rate": 0.0,
            }

        scenarios = self.db.query(ApiScenario).filter(
            ApiScenario.project_id == project_id,
            ApiScenario.id.in_(critical_ids),
            ApiScenario.is_deleted == False,
        ).all()

        total = len(critical_ids)
        covered = 0

        for sc in scenarios:
            steps = self.db.query(ApiScenarioStep).filter(
                ApiScenarioStep.scenario_id == sc.id,
                ApiScenarioStep.is_deleted == False,
            ).count()
            if steps > 0:
                covered += 1

        rate = round(covered / total * 100, 2) if total > 0 else 0.0

        return {
            "total_scenarios": total,
            "covered_scenarios": covered,
            "scenario_coverage_rate": rate,
        }

    def calculate_and_save(self, project_id: int, version_id: Optional[int] = None) -> dict:
        """计算覆盖率并保存快照"""
        from app.models.test_coverage import CoverageConfig, CoverageSnapshot
        from app.core.timezone import china_now_naive

        config = self.db.query(CoverageConfig).filter(
            CoverageConfig.project_id == project_id,
            CoverageConfig.is_deleted == False,
        ).first()

        excluded_paths = []
        excluded_methods = []
        critical_ids = []

        if config:
            excluded_paths = config.excluded_paths or []
            excluded_methods = config.excluded_methods or []
            critical_ids = config.critical_scenario_ids or []
            if not version_id:
                version_id = config.version_id

        api_result = self.calculate_api_coverage(
            project_id, version_id, excluded_paths, excluded_methods
        )
        scenario_result = self.calculate_scenario_coverage(project_id, critical_ids)

        snapshot = CoverageSnapshot(
            project_id=project_id,
            version_id=version_id,
            total_apis=api_result["total_apis"],
            covered_apis=api_result["covered_apis"],
            api_coverage_rate=api_result["api_coverage_rate"],
            uncovered_apis=api_result["uncovered_apis"],
            total_scenarios=scenario_result["total_scenarios"],
            covered_scenarios=scenario_result["covered_scenarios"],
            scenario_coverage_rate=scenario_result["scenario_coverage_rate"],
            total_cases=api_result["total_cases"],
            cases_with_api=api_result["cases_with_api"],
            coverage_matrix=api_result["coverage_matrix"],
            calculated_at=china_now_naive(),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        return {
            "snapshot_id": snapshot.id,
            "api_coverage_rate": snapshot.api_coverage_rate,
            "scenario_coverage_rate": snapshot.scenario_coverage_rate,
            "total_apis": snapshot.total_apis,
            "covered_apis": snapshot.covered_apis,
            "uncovered_apis": snapshot.uncovered_apis,
            "total_scenarios": snapshot.total_scenarios,
            "covered_scenarios": snapshot.covered_scenarios,
            "calculated_at": snapshot.calculated_at.isoformat() if snapshot.calculated_at else None,
        }

    def get_latest(self, project_id: int) -> Optional[dict]:
        """获取最新覆盖率快照"""
        from app.models.test_coverage import CoverageSnapshot

        snapshot = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.project_id == project_id,
        ).order_by(CoverageSnapshot.calculated_at.desc()).first()

        if not snapshot:
            return None

        return {
            "id": snapshot.id,
            "total_apis": snapshot.total_apis,
            "covered_apis": snapshot.covered_apis,
            "api_coverage_rate": snapshot.api_coverage_rate,
            "uncovered_apis": snapshot.uncovered_apis,
            "total_scenarios": snapshot.total_scenarios,
            "covered_scenarios": snapshot.covered_scenarios,
            "scenario_coverage_rate": snapshot.scenario_coverage_rate,
            "total_cases": snapshot.total_cases,
            "cases_with_api": snapshot.cases_with_api,
            "calculated_at": snapshot.calculated_at.isoformat() if snapshot.calculated_at else None,
        }

    def get_trend(self, project_id: int, days: int = 30) -> list:
        """获取覆盖率趋势"""
        from app.models.test_coverage import CoverageSnapshot
        from datetime import timedelta
        from app.core.timezone import china_now_naive

        cutoff = china_now_naive() - timedelta(days=days)
        snapshots = self.db.query(CoverageSnapshot).filter(
            CoverageSnapshot.project_id == project_id,
            CoverageSnapshot.calculated_at >= cutoff,
        ).order_by(CoverageSnapshot.calculated_at.asc()).all()

        return [
            {
                "date": s.calculated_at.strftime("%Y-%m-%d %H:%M") if s.calculated_at else "",
                "api_coverage_rate": s.api_coverage_rate,
                "scenario_coverage_rate": s.scenario_coverage_rate,
                "total_apis": s.total_apis,
                "covered_apis": s.covered_apis,
            }
            for s in snapshots
        ]

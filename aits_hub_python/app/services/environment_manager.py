import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """多环境管理器"""

    def __init__(self, db: Session):
        self.db = db

    def get_variables(self, project_id: int, environment_id: int) -> List[dict]:
        """获取环境变量列表"""
        from app.models.test_data_pool import EnvironmentVariableOverride

        vars = self.db.query(EnvironmentVariableOverride).filter(
            EnvironmentVariableOverride.project_id == project_id,
            EnvironmentVariableOverride.environment_id == environment_id,
        ).all()

        return [
            {
                "id": v.id,
                "key": v.key,
                "value": self._mask_value(v.value) if v.is_sensitive else v.value,
                "description": v.description,
                "is_sensitive": v.is_sensitive,
            }
            for v in vars
        ]

    def upsert_variable(
        self, project_id: int, environment_id: int, key: str, value: str, description: str = None, is_sensitive: bool = False
    ) -> dict:
        """创建或更新环境变量"""
        from app.models.test_data_pool import EnvironmentVariableOverride
        from app.core.timezone import china_now_naive

        existing = self.db.query(EnvironmentVariableOverride).filter(
            EnvironmentVariableOverride.project_id == project_id,
            EnvironmentVariableOverride.environment_id == environment_id,
            EnvironmentVariableOverride.key == key,
        ).first()

        if existing:
            existing.value = value
            if description is not None:
                existing.description = description
            existing.is_sensitive = is_sensitive
            existing.updated_at = china_now_naive()
            self.db.commit()
            self.db.refresh(existing)
            return {"id": existing.id, "key": existing.key, "action": "updated"}
        else:
            var = EnvironmentVariableOverride(
                project_id=project_id,
                environment_id=environment_id,
                key=key,
                value=value,
                description=description,
                is_sensitive=is_sensitive,
            )
            self.db.add(var)
            self.db.commit()
            self.db.refresh(var)
            return {"id": var.id, "key": var.key, "action": "created"}

    def delete_variable(self, project_id: int, variable_id: int) -> bool:
        """删除环境变量"""
        from app.models.test_data_pool import EnvironmentVariableOverride

        var = self.db.query(EnvironmentVariableOverride).filter(
            EnvironmentVariableOverride.id == variable_id,
            EnvironmentVariableOverride.project_id == project_id,
        ).first()

        if var:
            self.db.delete(var)
            self.db.commit()
            return True
        return False

    @staticmethod
    def _mask_value(value: str) -> str:
        """脱敏处理：保留前2后2字符，中间用****替代"""
        if not value:
            return value
        if len(value) <= 8:
            return "****"
        return f"{value[:2]}****{value[-2:]}"

    def compare_environments(self, project_id: int, env_ids: List[int]) -> dict:
        """对比多个环境的变量差异"""
        from app.models.test_data_pool import EnvironmentVariableOverride

        result = {
            "environments": env_ids,
            "all_keys": set(),
            "matrix": {},
            "diffs": [],
        }

        env_vars = {}
        sensitive_keys = set()
        for env_id in env_ids:
            vars = self.db.query(EnvironmentVariableOverride).filter(
                EnvironmentVariableOverride.project_id == project_id,
                EnvironmentVariableOverride.environment_id == env_id,
            ).all()
            env_vars[env_id] = {v.key: v.value for v in vars}
            for v in vars:
                if v.is_sensitive:
                    sensitive_keys.add(v.key)
            result["all_keys"].update(v.key for v in vars)

        for key in sorted(result["all_keys"]):
            row = {"key": key, "is_sensitive": key in sensitive_keys}
            values = []
            for env_id in env_ids:
                val = env_vars[env_id].get(key)
                if key in sensitive_keys:
                    row[f"env_{env_id}"] = self._mask_value(val) if val else val
                else:
                    row[f"env_{env_id}"] = val
                values.append(val)
            result["matrix"][key] = row

            if len(set(str(v) for v in values)) > 1:
                result["diffs"].append(row)

        result["all_keys"] = sorted(result["all_keys"])
        return result

    def clone_environment(
        self, project_id: int, source_env_id: int, target_env_id: int
    ) -> int:
        """克隆环境变量到目标环境"""
        from app.models.test_data_pool import EnvironmentVariableOverride

        source_vars = self.db.query(EnvironmentVariableOverride).filter(
            EnvironmentVariableOverride.project_id == project_id,
            EnvironmentVariableOverride.environment_id == source_env_id,
        ).all()

        count = 0
        for sv in source_vars:
            existing = self.db.query(EnvironmentVariableOverride).filter(
                EnvironmentVariableOverride.project_id == project_id,
                EnvironmentVariableOverride.environment_id == target_env_id,
                EnvironmentVariableOverride.key == sv.key,
            ).first()

            if not existing:
                var = EnvironmentVariableOverride(
                    project_id=project_id,
                    environment_id=target_env_id,
                    key=sv.key,
                    value=sv.value,
                    description=sv.description,
                    is_sensitive=sv.is_sensitive,
                )
                self.db.add(var)
                count += 1

        self.db.commit()
        return count

    def sync_variables(
        self, project_id: int, source_env_id: int, target_env_ids: List[int], keys: List[str] = None
    ) -> dict:
        """同步变量到目标环境"""
        from app.models.test_data_pool import EnvironmentVariableOverride
        from app.core.timezone import china_now_naive

        query = self.db.query(EnvironmentVariableOverride).filter(
            EnvironmentVariableOverride.project_id == project_id,
            EnvironmentVariableOverride.environment_id == source_env_id,
        )
        if keys:
            query = query.filter(EnvironmentVariableOverride.key.in_(keys))

        source_vars = query.all()
        result = {}

        for target_env_id in target_env_ids:
            synced = 0
            for sv in source_vars:
                existing = self.db.query(EnvironmentVariableOverride).filter(
                    EnvironmentVariableOverride.project_id == project_id,
                    EnvironmentVariableOverride.environment_id == target_env_id,
                    EnvironmentVariableOverride.key == sv.key,
                ).first()

                if existing:
                    existing.value = sv.value
                    existing.description = sv.description
                    existing.is_sensitive = sv.is_sensitive
                    existing.updated_at = china_now_naive()
                else:
                    var = EnvironmentVariableOverride(
                        project_id=project_id,
                        environment_id=target_env_id,
                        key=sv.key,
                        value=sv.value,
                        description=sv.description,
                        is_sensitive=sv.is_sensitive,
                    )
                    self.db.add(var)
                synced += 1
            result[target_env_id] = synced

        self.db.commit()
        return result

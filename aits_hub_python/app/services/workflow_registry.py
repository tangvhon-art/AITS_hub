"""
外部工作流模块注册表（Module Registry）

统一管理所有支持 workflow 接入的模块元信息，解决模块注册分散问题。
新增模块只需：
1. 实现 build_input / finalize / fallback 函数
2. 调用 register_module() 注册
3. 在 __init__.py 中 import 该模块确保注册执行

所有调用方（workflow_runner / workflow_finalize / workflow_tasks）统一从注册表获取，
不再需要在多个文件中重复维护 if-elif 分支。
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List

from sqlalchemy.orm import Session

from app.models.agent_task import AgentTask

logger = logging.getLogger(__name__)


@dataclass
class WorkflowModuleSpec:
    """单个工作流模块的完整规格定义"""
    module_id: str                                    # 模块唯一标识，如 "case.generate"
    agent_type: str                                   # 对应 AgentTask.agent_type
    display_name: str                                 # 中文显示名
    description: str = ""                             # 模块描述

    # input 构造函数：(db, task, module_id) -> input dict
    build_input: Optional[Callable[[Session, AgentTask, str], Dict[str, Any]]] = None

    # finalize 写库函数：(db, task, raw_content) -> None
    finalize: Optional[Callable[[Session, AgentTask, str], None]] = None

    # 降级 local 的 Celery task 函数（延迟导入，避免循环依赖）
    fallback_task: Optional[Callable] = None

    # 降级参数构造函数：(task) -> args tuple
    fallback_args_builder: Optional[Callable[[AgentTask], tuple]] = None

    # 降级时是否需要特殊处理（如 split_features 不基于 task_id）
    fallback_custom: bool = False


class WorkflowModuleRegistry:
    """工作流模块全局注册表"""
    _modules: Dict[str, WorkflowModuleSpec] = {}

    @classmethod
    def register(cls, spec: WorkflowModuleSpec):
        """注册模块（重复注册会覆盖并告警）"""
        if spec.module_id in cls._modules:
            logger.warning(f"[workflow_registry] 模块重复注册，将覆盖: {spec.module_id}")
        cls._modules[spec.module_id] = spec
        logger.info(f"[workflow_registry] 模块注册成功: {spec.module_id} ({spec.display_name})")

    @classmethod
    def get(cls, module_id: str) -> Optional[WorkflowModuleSpec]:
        return cls._modules.get(module_id)

    @classmethod
    def all_modules(cls) -> List[WorkflowModuleSpec]:
        return list(cls._modules.values())

    @classmethod
    def module_ids(cls) -> List[str]:
        return list(cls._modules.keys())

    @classmethod
    def agent_type_to_module(cls, agent_type: str) -> Optional[str]:
        """agent_type 反向查找 module_id"""
        for spec in cls._modules.values():
            if spec.agent_type == agent_type:
                return spec.module_id
        return None

    @classmethod
    def get_finalize_fn(cls, module_id: str) -> Optional[Callable]:
        """获取模块的 finalize 函数"""
        spec = cls.get(module_id)
        return spec.finalize if spec else None

    @classmethod
    def get_build_input_fn(cls, module_id: str) -> Optional[Callable]:
        """获取模块的 build_input 函数"""
        spec = cls.get(module_id)
        return spec.build_input if spec else None

    @classmethod
    def get_fallback(cls, module_id: str) -> Optional[tuple]:
        """获取模块的降级配置：(fallback_task, fallback_args_builder)"""
        spec = cls.get(module_id)
        if not spec or not spec.fallback_task:
            return None
        return (spec.fallback_task, spec.fallback_args_builder)

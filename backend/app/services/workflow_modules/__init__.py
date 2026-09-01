"""
外部工作流模块注册入口

import 此包时自动注册所有模块。
在 workflow_runner / workflow_finalize / workflow_tasks 中通过
`from app.services.workflow_modules import ensure_registered` 确保注册完成。
"""
from app.services.workflow_registry import WorkflowModuleRegistry, WorkflowModuleSpec

# 标记是否已注册（避免重复 import 导致重复注册日志）
_registered = False


def ensure_registered():
    """确保所有模块已注册（幂等）"""
    global _registered
    if _registered:
        return
    _register_all()
    _registered = True


def _register_all():
    """注册所有支持 workflow 的模块"""
    from app.services.workflow_runner import _build_requirement_input, _build_split_features_input
    from app.services.workflow_runner import _build_case_generate_input, _build_case_review_input, _build_report_generate_input
    from app.services.workflow_finalize import (
        finalize_requirement, finalize_split_features,
        finalize_cases, finalize_review, finalize_report,
    )
    from app.models.agent_task import AgentTask

    # ── 需求生成 ──
    WorkflowModuleRegistry.register(WorkflowModuleSpec(
        module_id="requirement.generate",
        agent_type="requirement_generator",
        display_name="需求生成",
        description="从描述生成结构化需求文档",
        build_input=_build_requirement_input,
        finalize=finalize_requirement,
        fallback_task=None,  # 延迟导入，在 fallback_args_builder 中处理
        fallback_args_builder=lambda task: (task.id,),
    ))

    # ── 功能点拆分 ──
    def _split_fallback_args(task: AgentTask) -> tuple:
        req_id = (task.input_params or {}).get("requirement_id")
        return (req_id, task.llm_config_id) if req_id else ()

    WorkflowModuleRegistry.register(WorkflowModuleSpec(
        module_id="requirement.split_features",
        agent_type="feature_splitter",
        display_name="功能点拆分",
        description="从需求拆分功能点（按模块分组）",
        build_input=_build_split_features_input,
        finalize=finalize_split_features,
        fallback_args_builder=_split_fallback_args,
        fallback_custom=True,
    ))

    # ── 用例生成 ──
    WorkflowModuleRegistry.register(WorkflowModuleSpec(
        module_id="case.generate",
        agent_type="case_generator",
        display_name="用例生成",
        description="从需求/功能点生成测试用例",
        build_input=_build_case_generate_input,
        finalize=finalize_cases,
        fallback_args_builder=lambda task: (task.id,),
    ))

    # ── 用例评审 ──
    WorkflowModuleRegistry.register(WorkflowModuleSpec(
        module_id="case.review",
        agent_type="case_reviewer",
        display_name="用例评审",
        description="对用例进行7维度AI评审",
        build_input=_build_case_review_input,
        finalize=finalize_review,
        fallback_args_builder=lambda task: (task.id,),
    ))

    # ── 测试报告生成 ──
    def _report_fallback_args(task: AgentTask) -> tuple:
        params = task.input_params or {}
        return (
            params.get("report_id"),
            task.project_id,
            params.get("report_type", "full"),
            params.get("version_id"),
            params.get("title", "测试报告"),
            task.llm_config_id,
            task.id,
        )

    WorkflowModuleRegistry.register(WorkflowModuleSpec(
        module_id="report.generate",
        agent_type="report_generator",
        display_name="测试报告生成",
        description="AI生成测试报告（统计数据+AI增强）",
        build_input=_build_report_generate_input,
        finalize=finalize_report,
        fallback_args_builder=_report_fallback_args,
    ))

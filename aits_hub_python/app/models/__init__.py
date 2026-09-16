from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import TestRequirement, RequirementFeature
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.agent_task import AgentTask
from app.models.llm_config import LLMConfig
from app.models.defect import Defect
from app.models.report import TestReport
from app.models.knowledge_doc import KnowledgeDoc
from app.models.test_plan import TestPlan, TestPlanCase, TestEnvironment, TestPlanItem, TestPlanExecution, TestPlanExecutionResult
from app.models.audit_log import AuditLog
from app.models.sys_crontab import SysCrontab
from app.models.celery_task_log import CeleryTaskLog
from app.models.project_version import ProjectVersion
from app.models.automation_script import AutomationScript
from app.models.automation_suite import (
    AutomationSuite,
    AutomationSuiteStep,
    AutomationSuiteRun,
    AutomationSuiteRunResult,
)
from app.models.api_test import (
    ApiModule,
    ApiDefinition,
    ApiTestCase,
    ApiCaseAssertion,
    ApiScenario,
    ApiScenarioStep,
    ApiScenarioVariable,
    ApiExecution,
    ApiExecutionResult,
    ApiMockExpectation,
    ApiDebugHistory,
)
from app.models.performance_test import PerformanceTest, PerformanceTestRun
from app.models.test_coverage import CoverageConfig, CoverageSnapshot
from app.models.test_data_pool import TestDataPool, EnvironmentVariableOverride
from app.models.prompt import Prompt
from app.models.notification import NotificationChannel, NotificationRule, NotificationRecord
from app.models.mcp_connector import MCPConnector
from app.models.skill import Skill
from app.models.chat_history import ChatSession, ChatMessage
from app.models.ui_healing import UIPageVisit, UIPageProfile, UIElementFingerprint, UIHealingRecord
from app.models.workflow import (
    WorkflowPlatformConnector,
    WorkflowWebhookConfig,
    AgentBackendConfig,
    WorkflowCallLog,
    WorkflowInputMapping,
)
from app.models.eval import (
    EvalTarget,
    EvalDataset,
    EvalCase,
    EvalTask,
    EvalRun,
    EvalResult,
    EvalReport,
    EvalIssue,
    EvalBaseline,
)

__all__ = [
    "User",
    "Project",
    "ProjectMember",
    "TestRequirement",
    "RequirementFeature",
    "TestCase",
    "TestRun",
    "AgentTask",
    "LLMConfig",
    "Defect",
    "TestReport",
    "KnowledgeDoc",
    "TestPlan",
    "TestPlanCase",
    "TestEnvironment",
    "TestPlanItem",
    "TestPlanExecution",
    "TestPlanExecutionResult",
    "AuditLog",
    "ProjectVersion",
    "AutomationScript",
    "AutomationSuite",
    "AutomationSuiteStep",
    "AutomationSuiteRun",
    "AutomationSuiteRunResult",
    "ApiModule",
    "ApiDefinition",
    "ApiTestCase",
    "ApiCaseAssertion",
    "ApiScenario",
    "ApiScenarioStep",
    "ApiScenarioVariable",
    "ApiExecution",
    "ApiExecutionResult",
    "ApiMockExpectation",
    "ApiDebugHistory",
    "PerformanceTest",
    "PerformanceTestRun",
    "CoverageConfig",
    "CoverageSnapshot",
    "TestDataPool",
    "EnvironmentVariableOverride",
    "Prompt",
    "NotificationChannel",
    "NotificationRule",
    "NotificationRecord",
    "MCPConnector",
    "Skill",
    "ChatSession",
    "ChatMessage",
    "UIPageVisit",
    "UIPageProfile",
    "UIElementFingerprint",
    "UIHealingRecord",
    "SysCrontab",
    "CeleryTaskLog",
    "WorkflowPlatformConnector",
    "WorkflowWebhookConfig",
    "AgentBackendConfig",
    "WorkflowCallLog",
    "WorkflowInputMapping",
]

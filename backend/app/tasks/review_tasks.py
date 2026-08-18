"""
用例评审 Celery 任务
"""
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.agents.case_reviewer import CaseReviewerAgent
from app.services.content_extractor import ContentExtractor
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="review_cases", max_retries=2)
def review_cases_task(self, task_id: int):
    """AI 用例评审任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        task.status = "running"
        db.commit()

        input_params = task.input_params or {}
        cases = input_params.get("cases", [])
        requirement = input_params.get("requirement", "")
        prompt_id = input_params.get("prompt_id")

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"用例评审使用自定义 Prompt: {prompt_obj.name}")

        # 执行评审
        reviewer = CaseReviewerAgent(
            db, llm_config_id=task.llm_config_id, task_id=task.id, project_id=task.project_id
        )
        agent_result = reviewer.review(cases, requirement=requirement, system_prompt=system_prompt)

        from app.services.content_extractor import ContentExtractor
        extracted = ContentExtractor.extract_review(agent_result["raw_content"])
        result = {
            **extracted,
            "token_usage": agent_result.get("token_usage", {}),
            "llm_config_id": agent_result.get("llm_config_id"),
        }

        task.status = "success"
        task.output_result = result
        task.token_usage = result.get("token_usage", {})
        task.llm_config_id = result.get("llm_config_id")
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"用例评审任务完成: task_id={task_id}, score={result.get('score')}")

        # 发送评审完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                task.project_id,
                "ai.case_review.completed",
                {
                    "score": result.get("score"),
                    "passed": result.get("passed"),
                    "case_count": len(cases),
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送用例评审通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"用例评审任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = china_now_naive()
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="用例评审",
                    error=str(e),
                    related_object="用例评审",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()


# ===== 评审优化用例 =====

OPTIMIZE_CASES_SYSTEM_PROMPT = """你是一名资深软件测试工程师。请根据用例评审报告中发现的问题和改进建议，对现有测试用例进行优化，并补充缺失的测试用例。

## 输出格式（最高优先级，必须严格遵守）

你必须且只能输出一个合法的 JSON 对象，包含以下结构：

{"cases": [{"title": "用例标题", "module": "所属模块", "priority": "P0/P1/P2/P3", "case_type": "functional/exception/boundary/performance/security", "preconditions": "前置条件", "steps": [{"action": "操作步骤", "expected": "预期结果"}], "expected_result": "最终预期结果", "bdd_content": ""}]}

### 绝对禁止
1. 禁止使用 ```json ``` 等 Markdown 代码块包裹输出
2. 禁止在 JSON 前后添加任何解释、前言、注释或空行
3. 输出的第一个字符必须是 {，最后一个字符必须是 }
4. 所有内容使用中文
5. steps 数组中每个元素必须包含 action 和 expected 字段

## 优化原则
- 针对评审报告中的每个问题，修正对应用例的不足
- 根据整体改进建议，补充缺失的测试场景（边界值、异常流程、安全等）
- 优化后的用例步骤必须清晰可执行，预期结果必须明确可验证
- 保持与原有用例相同的模块归属
- 优先级根据问题严重程度调整：high 问题对应的用例设为 P0/P1"""

OPTIMIZE_CASES_USER_PROMPT = """## 原始需求
{requirement}

## 模块范围
{module_info}

## 现有测试用例
{cases_json}

## 评审发现的问题
{issues_json}

## 整体改进建议
{suggestions_json}

## 优化模式
{mode_desc}

请根据以上评审结果，输出优化和补充后的完整测试用例列表（包含修正后的原有问题用例和新增的补充用例）。"""


@celery_app.task(bind=True, name="optimize_cases_from_review", max_retries=0)
def optimize_cases_from_review_task(
    self,
    review_task_id: int,
    optimize_task_id: int,
):
    """基于评审结果优化/补充用例的异步任务"""
    db = SessionLocal()
    try:
        opt_task = db.query(AgentTask).filter(AgentTask.id == optimize_task_id).first()
        if not opt_task:
            logger.error(f"优化任务不存在: {optimize_task_id}")
            return

        opt_task.status = "running"
        db.commit()

        # 加载评审任务
        review_task = db.query(AgentTask).filter(AgentTask.id == review_task_id).first()
        if not review_task:
            raise ValueError(f"评审任务不存在: {review_task_id}")

        review_input = review_task.input_params or {}
        review_output = review_task.output_result or {}

        project_id = opt_task.project_id
        requirement_id = review_input.get("requirement_id")
        module_filter = review_input.get("module")
        original_cases = review_input.get("cases", [])
        requirement_text = review_input.get("requirement", "")
        issues = review_output.get("issues", [])
        suggestions = review_output.get("overall_suggestions", [])

        opt_params = opt_task.input_params or {}
        optimize_mode = opt_params.get("optimize_mode", "both")
        custom_system_prompt = opt_params.get("system_prompt", "")
        prompt_id = opt_params.get("prompt_id")

        # 获取自定义 Prompt
        system_prompt = custom_system_prompt or OPTIMIZE_CASES_SYSTEM_PROMPT
        if prompt_id and not custom_system_prompt:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or OPTIMIZE_CASES_SYSTEM_PROMPT

        # 模式描述
        mode_map = {
            "optimize": "仅优化评审中发现问题的用例，不新增用例",
            "supplement": "仅根据改进建议补充缺失的测试场景，保留原有正常用例",
            "both": "既优化问题用例，也补充缺失的测试场景",
        }
        mode_desc = mode_map.get(optimize_mode, mode_map["both"])

        module_info = f"仅限模块：{module_filter}" if module_filter else "根据需求功能划分模块"

        import json
        user_content = OPTIMIZE_CASES_USER_PROMPT.format(
            requirement=requirement_text or "（无）",
            module_info=module_info,
            cases_json=json.dumps(original_cases, ensure_ascii=False, indent=2),
            issues_json=json.dumps(issues, ensure_ascii=False, indent=2),
            suggestions_json=json.dumps(suggestions, ensure_ascii=False, indent=2),
            mode_desc=mode_desc,
        )

        # 调用 LLM
        from langchain_core.messages import SystemMessage, HumanMessage
        from app.agents.llm_factory import llm_factory

        llm, used_config = llm_factory.get_llm_with_fallback(
            db, preferred_config_id=opt_task.llm_config_id
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        response = llm.invoke(messages)
        raw_content = response.content if hasattr(response, "content") else str(response)

        # 解析用例
        from app.agents.utils import extract_json
        parsed = extract_json(raw_content)
        cases = []
        if parsed and isinstance(parsed, dict):
            cases = parsed.get("cases", [])
        if not cases:
            cases = ContentExtractor.extract_test_cases(raw_content)

        if not cases:
            raise ValueError("未能从 AI 返回中解析出有效用例")

        # 如果指定了模块筛选，确保所有用例归属该模块
        if module_filter:
            for c in cases:
                if not c.get("module"):
                    c["module"] = module_filter

        # 保存用例
        from app.services.ai_creation_service import AICreationService
        created_cases = AICreationService.create_test_cases(
            db,
            project_id=project_id,
            cases=cases,
            requirement_id=requirement_id,
            created_by=opt_task.created_by,
        )

        opt_task.status = "success"
        opt_task.output_result = {
            "review_task_id": review_task_id,
            "optimize_mode": optimize_mode,
            "case_count": len(cases),
            "cases_saved": len(created_cases),
            "requirement_id": requirement_id,
            "module": module_filter,
            "saved_case_ids": [c.id for c in created_cases],
        }
        opt_task.completed_at = china_now_naive()
        db.commit()

        logger.info(
            f"评审优化用例完成: review={review_task_id}, "
            f"generated={len(cases)}, saved={len(created_cases)}"
        )

        # 发送通知
        try:
            duration = 0.0
            if opt_task.created_at and opt_task.completed_at:
                duration = round((opt_task.completed_at - opt_task.created_at).total_seconds(), 2)
            notify_event(
                project_id,
                "ai.case.generated",
                {
                    "source_name": "评审优化",
                    "strategy": optimize_mode,
                    "success_count": len(created_cases),
                    "failed_count": len(cases) - len(created_cases),
                    "duration": duration,
                },
                triggered_by=opt_task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送评审优化通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"评审优化用例任务失败: {e}", exc_info=True)
        try:
            opt_task = db.query(AgentTask).filter(AgentTask.id == optimize_task_id).first()
            if opt_task:
                opt_task.status = "failed"
                opt_task.error_message = str(e)[:500]
                opt_task.completed_at = china_now_naive()
                db.commit()
                notify_ai_task_failed(
                    opt_task.project_id,
                    task_type="评审优化用例",
                    error=str(e),
                    related_object="评审报告优化",
                    triggered_by=opt_task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()

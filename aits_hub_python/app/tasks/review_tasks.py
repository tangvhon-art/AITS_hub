"""
用例评审 Celery 任务
"""
import logging

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.agents.case_reviewer import REVIEW_SYSTEM_PROMPT
from app.services.content_extractor import ContentExtractor
from app.services.notification_service import notify_event, notify_ai_task_failed
from app.services.workflow_connector import WorkflowInvokeError
from app.services.workflow_runner import run as workflow_run
from app.services.agent_backend_dispatcher import resolve_backend
from app.services.agent_task_status import mark_running, finalize_agent_task

logger = logging.getLogger(__name__)

MODULE_ID = "case.review"


class ReviewCasesTask(BaseTask):
    """AI 用例评审任务 — 直接使用 call_with_fallback，不经过 CaseReviewerAgent"""

    task_name = "review_cases"

    def execute(self, db, task_id: int) -> dict:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return {"status": "aborted", "reason": "agent_task_not_found"}

        # ── 执行后端分发：页面选择优先 → 模块配置 → local ──
        page_choice = (task.input_params or {}).get("page_backend")
        backend = resolve_backend(db, MODULE_ID, task.project_id, page_choice=page_choice)
        task.backend = backend
        db.commit()

        if backend == "workflow":
            try:
                workflow_run(db, task, MODULE_ID)
                # 受理成功：任务挂起，等待 Webhook 回调（不执行本地 LLM）
                return {"status": "pending_workflow"}
            except WorkflowInvokeError as e:
                logger.warning(f"用例评审 workflow 调用失败，降级 local: {e}")
                task.backend = "local"
                task.status = "pending"
                task.error_message = f"workflow 降级: {e}"[:500]
                db.commit()
                # fall through 到 local 逻辑

        task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, task):
            db.commit()
            logger.info(f"用例评审任务已被取消，中止执行: task_id={task_id}")
            return {"status": "aborted", "reason": "cancelled"}

        input_params = task.input_params or {}
        cases = input_params.get("cases", [])
        requirements = input_params.get("requirements", [])
        groups = input_params.get("groups", [])
        prompt_id = input_params.get("prompt_id")

        # 兼容旧版：单个 requirement 文本
        requirement_text = input_params.get("requirement", "")
        if requirements:
            req_parts = []
            for r in requirements:
                req_parts.append(f"【需求：{r.get('title', '')}】\n{r.get('content', '')}")
            requirement_text = "\n\n".join(req_parts)

        # 需求ID → 需求名称映射：优先取输入参数，缺失时查库兜底，
        # 供 HUMAN 消息展示需求名称及回填 issue 的 requirement_title
        req_title_map = {}
        for r in requirements:
            if r.get("id") is not None and r.get("title"):
                req_title_map[r["id"]] = r["title"]
        for g in groups:
            rid = g.get("requirement_id")
            if rid is not None and g.get("requirement_title") and not req_title_map.get(rid):
                req_title_map[rid] = g["requirement_title"]
        missing_ids = {c.get("req_id") for c in cases if c.get("req_id") and c.get("req_id") not in req_title_map}
        if missing_ids:
            from app.models.requirement import TestRequirement
            rows = db.query(TestRequirement.id, TestRequirement.title).filter(
                TestRequirement.id.in_(list(missing_ids)),
                TestRequirement.is_deleted == False,
            ).all()
            for rid, title in rows:
                if title:
                    req_title_map[rid] = title

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"用例评审使用自定义 Prompt: {prompt_obj.name}")

        if not system_prompt:
            system_prompt = REVIEW_SYSTEM_PROMPT

        # 构建 human 消息
        human_text = _build_review_human_text(cases, requirement_text, groups, req_title_map)

        # 直接调用 LLM — 使用 call_with_fallback（同用例生成路径）
        from langchain_core.messages import SystemMessage, HumanMessage
        from app.agents.llm_factory import llm_factory

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_text),
        ]

        logger.info(f"[review_cases] 开始调用 LLM, cases={len(cases)}, messages={len(messages)}")

        import time
        start = time.time()
        response, token_usage, used_config_id = llm_factory.call_with_fallback(
            db,
            messages,
            preferred_config_id=task.llm_config_id,
            max_tokens=16384,
            temperature=0.2,
        )
        elapsed = time.time() - start

        raw_content = response.content if hasattr(response, "content") else str(response)
        logger.info(
            f"[review_cases] LLM 调用完成: elapsed={elapsed:.1f}s, "
            f"content_len={len(raw_content)}, tokens={token_usage}, config_id={used_config_id}"
        )
        logger.info(f"[review_cases] raw_content 前300字: {raw_content[:300]}")

        # 解析 Markdown 评审结果
        from app.services.content_extractor import ContentExtractor
        extracted = ContentExtractor.extract_review(raw_content)

        # 回填 issue 中缺失的 module / requirement_title：基于原始用例数据
        issues = extracted.get("issues", [])
        if issues:
            # 构建 case_id → {module, requirement_title} 映射
            case_meta_map = {}
            for case in cases:
                cid = case.get("id")
                if cid is not None:
                    case_meta_map[cid] = {
                        "module": case.get("module", "") or "",
                        "requirement_title": req_title_map.get(case.get("req_id"), "") or "",
                    }

            filled_count = 0
            for issue in issues:
                cid = issue.get("case_id")
                if cid is not None and cid in case_meta_map:
                    meta = case_meta_map[cid]
                    # module 仅在为空时回填；requirement_title 若为"需求ID=x"占位符则用真实名称覆盖
                    if not issue.get("module"):
                        issue["module"] = meta["module"]
                    cur_title = (issue.get("requirement_title") or "").strip()
                    if meta["requirement_title"] and (
                        not cur_title
                        or "需求ID=" in cur_title
                        or cur_title == "未关联需求"
                    ):
                        issue["requirement_title"] = meta["requirement_title"]
                    filled_count += 1
            if filled_count:
                logger.info(f"[review_cases] 回填 issue 元数据: {filled_count}/{len(issues)} 条")

        result = {
            **extracted,
            "token_usage": token_usage,
            "llm_config_id": used_config_id,
            "raw_content": raw_content,
        }

        logger.info(
            f"[review_cases] 解析完成: score={result.get('score')}, "
            f"issues={len(result.get('issues', []))}, "
            f"suggestions={len(result.get('overall_suggestions', []))}, "
            f"missing={len(result.get('missing_scenarios', []))}"
        )

        finalize_agent_task(db, task, "success")
        task.output_result = result
        task.token_usage = token_usage
        task.llm_config_id = used_config_id
        db.commit()

        logger.info(f"用例评审任务完成: task_id={task_id}, score={result.get('score')}")

        return {
            "status": "success",
            "task_id": task_id,
            "project_id": task.project_id,
            "created_by": task.created_by,
            "score": result.get("score"),
            "passed": result.get("passed"),
            "case_count": len(cases),
        }

    def on_success(self, db, result: dict, task_id: int) -> None:
        if result.get("status") != "success":
            return

        # 发送评审完成通知
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                result.get("project_id"),
                "ai.case_review.completed",
                {
                    "score": result.get("score"),
                    "passed": result.get("passed"),
                    "case_count": result.get("case_count", 0),
                    "duration": duration,
                },
                triggered_by=result.get("created_by"),
            )
        except Exception as notify_e:
            logger.warning(f"发送用例评审通知失败: {notify_e}")

    def on_failure(self, db, error: Exception, task_id: int) -> None:
        logger.error(f"用例评审任务失败: task_id={task_id}, error={error}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                finalize_agent_task(db, task, "failed", str(error))
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="用例评审",
                    error=str(error),
                    related_object="用例评审",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass


def _build_review_human_text(cases, requirement, groups, req_title_map=None):
    """构建评审 HUMAN 消息"""
    parts = []

    if requirement and requirement.strip():
        parts.append("## 需求描述")
        parts.append(requirement.strip())
        parts.append("")

    if groups and len(groups) > 0:
        parts.append("## 分组概览")
        for i, g in enumerate(groups, 1):
            parts.append(f"{i}. 需求：{g.get('requirement_title', '未知')} | 模块：{g.get('module', '未分类')} | 用例数：{g.get('case_count', 0)}")
        parts.append("")

    parts.append("## 待评审用例（每条标注数据库ID/需求/功能点，重复判定依据三者一致性）")
    for case in cases:
        case_id = case.get("id")
        parts.append(f"\n用例[{case_id}]：{case.get('title', '（无标题）')}")
        parts.append(f"  模块：{case.get('module', '未设置')}")
        # 需求与功能点信息：用于重复判定
        req_id = case.get("req_id")
        feature_name = case.get("feature_name", "")
        feature_module = case.get("feature_module", "")
        req_title = (req_title_map or {}).get(req_id, "") if req_id else ""
        if req_title:
            req_label = f"{req_title}（需求ID={req_id}）"
        else:
            req_label = f"需求ID={req_id}" if req_id else "未关联需求"
        if feature_name:
            feat_label = f"功能点={feature_name}"
        elif feature_module:
            feat_label = f"功能点模块={feature_module}"
        else:
            feat_label = "未关联功能点"
        parts.append(f"  需求：{req_label}")
        parts.append(f"  功能点：{feat_label}")
        _type_map = {"functional": "功能测试", "performance": "性能测试", "security": "安全测试"}
        parts.append(f"  类型：{_type_map.get(case.get('case_type', 'functional'), case.get('case_type', '功能测试'))}")
        parts.append(f"  优先级：{case.get('priority', '未设置')}")
        pre = case.get("preconditions", "")
        parts.append(f"  前置条件：{pre if pre else '（无）'}")
        steps = case.get("steps", [])
        if steps and len(steps) > 0:
            parts.append("  步骤：")
            for si, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    action = step.get("action", "")
                    expected = step.get("expected", "")
                    parts.append(f"    {si}. {action} → 预期：{expected}")
                else:
                    parts.append(f"    {si}. {str(step)}")
        else:
            parts.append("  步骤：（无）")
        exp = case.get("expected_result", "")
        parts.append(f"  预期结果：{exp if exp else '（无）'}")

    parts.append("")
    parts.append("请根据以上用例数据进行评审，按照输出格式输出 Markdown 评审结果。")
    return "\n".join(parts)


# ===== 评审优化用例 =====

OPTIMIZE_CASES_SYSTEM_PROMPT = """你是一名资深软件测试工程师。请根据用例评审报告中发现的问题和改进建议，对现有测试用例进行优化，并补充缺失的测试用例。

## 输出格式（最高优先级）
输出两个 Markdown 表格，用 ## 标题分隔。不要输出任何其他内容。

## 优化用例（更新已有问题用例）
| original_case_id | title | module | priority | preconditions | action | expected | expected_result |
|------------------|-------|--------|----------|---------------|--------|----------|-----------------|
| 15 | 测试完整登录流程 | 登录模块 | P0 | 用户已注册账号admin/123456 | 1. 打开登录页面 2. 输入用户名admin 3. 输入密码123456 4. 点击登录按钮 | 1. 登录页面正常显示 2. 用户名输入框显示admin 3. 密码输入框显示掩码 4. 页面跳转到首页 | 成功登录并跳转到首页 |
| 22 | 异常场景-密码错误 | 登录模块 | P1 | 用户已注册账号admin | 1. 打开登录页面 2. 输入用户名admin 3. 输入错误密码xxx123 4. 点击登录按钮 | 1. 登录页面正常显示 2. 用户名输入框显示admin 3. 密码输入框显示掩码 4. 页面显示密码错误 | 登录失败提示密码错误 |

## 补充用例（新增缺失场景）
| title | module | priority | preconditions | action | expected | expected_result |
|-------|--------|----------|---------------|--------|----------|-----------------|
| 边界值-密码长度最小值6位 | 登录模块 | P1 | 用户已注册账号admin | 1. 打开登录页面 2. 输入用户名admin 3. 输入6位密码abc123 4. 点击登录按钮 | 1. 登录页面正常显示 2. 用户名输入框显示admin 3. 密码输入框显示掩码 4. 登录成功跳转首页 | 登录成功 |
| 异常场景-SQL注入用户名 | 登录模块 | P0 | 系统已部署安全防护 | 1. 打开登录页面 2. 输入用户名admin OR 1=1 3. 输入密码123456 4. 点击登录按钮 | 1. 登录页面正常显示 2. 输入框接受特殊字符 3. 密码输入框显示掩码 4. 系统拒绝登录 | 阻止SQL注入攻击 |

## 规则
1. 只输出表格，不要输出标题、解释、代码块标记
2. 每行一条用例，字段用 | 分隔
3. action 和 expected 必须包含完整的操作步骤，用 1. 2. 3. 编号，每个步骤之间用空格分隔
4. action 和 expected 的步骤要一一对应
5. 优化用例表格的 original_case_id 必须是现有用例的真实ID
6. 补充用例表格不需要 original_case_id
7. 优先级用 P0/P1/P2/P3
8. module 必须与原有用例保持一致
9. 如果优化模式为 supplement（仅补充），则优化用例表格输出空表格（只有表头）
10. 如果优化模式为 optimize（仅优化），则补充用例表格输出空表格（只有表头）
11. 所有内容使用中文
12. 【关键】每行数据的列数必须与表头完全一致，缺少的列必须用空值占位（即 ||），不得跳过任何列。尤其 module 列不能省略，如果无法确定模块名则输出空值
13. 【关键-补充用例 title 规范】补充用例的 title 字段必须是测试场景描述（如"测试SQL注入攻击防护"、"验证XSS过滤功能"、"检查边界值处理"），禁止仅填写模块名（如"用户反馈管理"、"规则配置管理"等）。title 应以"测试/验证/检查/确保/确认/校验/边界/异常"等动词开头，描述具体的测试场景。"""

OPTIMIZE_CASES_USER_PROMPT = """## 原始需求
{requirement}

## 模块范围
{module_info}

## 现有测试用例（每条包含 id 字段，优化用例的 original_case_id 必须引用这些 id）
{cases_json}

## 评审发现的问题
{issues_json}

## 整体改进建议
{suggestions_json}

## 遗漏场景
{missing_json}

## 优化模式
{mode_desc}

请根据以上评审结果输出两个 Markdown 表格：优化用例表格和补充用例表格。"""


class OptimizeCasesFromReviewTask(BaseTask):
    """基于评审结果优化/补充用例的异步任务"""

    task_name = "optimize_cases_from_review"

    def execute(self, db, review_task_id: int, optimize_task_id: int) -> dict:
        opt_task = db.query(AgentTask).filter(AgentTask.id == optimize_task_id).first()
        if not opt_task:
            logger.error(f"优化任务不存在: {optimize_task_id}")
            return {"status": "aborted", "reason": "opt_task_not_found"}

        opt_task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, opt_task):
            db.commit()
            logger.info(f"用例优化任务已被取消，中止执行: task_id={optimize_task_id}")
            return {"status": "aborted", "reason": "cancelled"}

        # 加载评审任务
        review_task = db.query(AgentTask).filter(AgentTask.id == review_task_id).first()
        if not review_task:
            raise ValueError(f"评审任务不存在: {review_task_id}")

        review_input = review_task.input_params or {}
        review_output = review_task.output_result or {}

        project_id = opt_task.project_id
        requirement_id = review_input.get("requirement_id")
        module_filter = review_input.get("module")
        requirement_ids = review_input.get("requirement_ids") or []
        modules_list = review_input.get("modules") or []
        groups = review_input.get("groups") or []
        if not module_filter and modules_list:
            module_filter = modules_list[0]

        def _resolve_req_id(case_module=None):
            """推导补充用例应关联的需求ID：单需求直接用；多需求按模块匹配分组，兜底取第一个"""
            if requirement_id:
                return requirement_id
            if len(requirement_ids) == 1:
                return requirement_ids[0]
            target_module = case_module or module_filter
            if target_module and groups:
                for g in groups:
                    if g.get("module") == target_module and g.get("requirement_id"):
                        return g.get("requirement_id")
            return requirement_ids[0] if requirement_ids else None
        original_cases = review_input.get("cases", [])
        requirement_text = review_input.get("requirement", "")
        issues = review_output.get("issues", [])
        suggestions = review_output.get("overall_suggestions", [])
        missing_scenarios = review_output.get("missing_scenarios", [])

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
            missing_json=json.dumps(missing_scenarios, ensure_ascii=False, indent=2) if missing_scenarios else "（无）",
            mode_desc=mode_desc,
        )

        # 调用 LLM — 使用 call_with_fallback 支持 max_tokens 和降级
        from langchain_core.messages import SystemMessage, HumanMessage
        from app.agents.llm_factory import llm_factory

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        response, token_usage, used_config_id = llm_factory.call_with_fallback(
            db,
            messages,
            preferred_config_id=opt_task.llm_config_id,
            max_tokens=8192,
        )
        raw_content = response.content if hasattr(response, "content") else str(response)
        logger.info(f"评审优化 LLM 调用完成, content_len={len(raw_content)}, tokens={token_usage}")

        # 解析用例 — 优先尝试 JSON（旧格式兼容），否则用 Markdown 解析
        from app.agents.utils import extract_json
        from app.agents.case_generator import CaseGeneratorAgent

        optimized_cases = []
        new_cases = []

        parsed = extract_json(raw_content)
        if parsed and isinstance(parsed, dict):
            # 旧 JSON 格式
            optimized_cases = parsed.get("optimized_cases", [])
            new_cases = parsed.get("new_cases", [])
            if not optimized_cases and not new_cases:
                new_cases = parsed.get("cases", [])
        else:
            # 新 Markdown 格式 — 按 ## 标题分割
            import re
            clean = raw_content.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```\w*\n?', '', clean)
                clean = re.sub(r'\n?```$', '', clean)

            sections = re.split(r'\n##+\s*', clean)
            sections = [s.strip() for s in sections if s.strip()]

            for section in sections:
                first_line = section.split('\n')[0].strip().lower()
                if '优化' in first_line and ('用例' in first_line or 'case' in first_line):
                    # 优化用例表格
                    features = [{"name": "", "module_name": "", "priority": ""}]
                    cases_parsed = CaseGeneratorAgent._parse_markdown_cases(section, features)
                    for c in cases_parsed:
                        # 提取 original_case_id
                        # 查找表格中的 original_case_id 列
                        lines = section.split('\n')
                        for line in lines:
                            if line.strip().startswith('|') and 'original_case_id' in line.lower():
                                header_cells = [cell.strip().lower() for cell in line.split('|')[1:-1]]
                                break
                        else:
                            header_cells = []

                        # 从原始数据行中提取 original_case_id
                        if 'original_case_id' not in header_cells and 'original_case_id' not in str(c).lower():
                            c.pop('original_case_id', None)

                        # 尝试从 case dict 中获取
                        oid = c.get('original_case_id')
                        if oid is not None:
                            try:
                                c['original_case_id'] = int(oid)
                            except (ValueError, TypeError):
                                pass
                        optimized_cases.append(c)

                elif '补充' in first_line or '新增' in first_line:
                    # 补充用例表格
                    features = [{"name": "", "module_name": "", "priority": ""}]
                    cases_parsed = CaseGeneratorAgent._parse_markdown_cases(section, features)
                    new_cases.extend(cases_parsed)

        logger.info(f"评审优化解析: optimized={len(optimized_cases)}, new={len(new_cases)}")

        # 如果两种格式都解析失败
        if not optimized_cases and not new_cases:
            # 最后尝试整体当 Markdown 解析
            features = [{"name": "", "module_name": "", "priority": ""}]
            all_cases = CaseGeneratorAgent._parse_markdown_cases(raw_content, features)
            new_cases = all_cases
            if not new_cases:
                raise ValueError("未能从 AI 返回中解析出有效用例")

        # 如果指定了模块筛选，确保所有用例归属该模块
        if module_filter:
            for c in optimized_cases + new_cases:
                if not c.get("module"):
                    c["module"] = module_filter

        # 1. 更新优化用例（原有问题用例）
        from app.models.test_case import TestCase
        updated_count = 0
        updated_case_ids = []
        for c in optimized_cases:
            original_id = c.get("original_case_id")
            if not original_id:
                continue
            existing = db.query(TestCase).filter(
                TestCase.id == original_id,
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
            ).first()
            if not existing:
                continue
            if c.get("title"):
                existing.title = c["title"]
            if c.get("module") is not None:
                existing.module = c["module"]
            if c.get("priority"):
                existing.priority = c["priority"]
            if c.get("case_type"):
                existing.case_type = c["case_type"]
            if c.get("preconditions") is not None:
                existing.preconditions = c["preconditions"]
            if c.get("steps") is not None:
                import json as _json
                existing.steps = _json.dumps(c["steps"], ensure_ascii=False) if isinstance(c["steps"], list) else str(c["steps"])
            if c.get("expected_result") is not None:
                existing.expected_result = c["expected_result"]
            if c.get("bdd_content") is not None:
                existing.bdd_content = c["bdd_content"]
            existing.needs_update = False
            existing.updated_at = china_now_naive()
            updated_count += 1
            updated_case_ids.append(original_id)

        # 2. 创建补充用例（新增缺失场景）
        from app.services.ai_creation_service import AICreationService
        created_cases = []
        if new_cases:
            # 二次校验：修复补充用例的 title/module 错位
            from app.agents.case_generator import CaseGeneratorAgent
            fixed_count = 0
            for c in new_cases:
                old_title = c.get("title", "")
                CaseGeneratorAgent._fix_title_module_swap(c)
                if c.get("title") != old_title:
                    fixed_count += 1
            if fixed_count:
                logger.info(f"[optimize_cases] 二次修复 title/module 错位: {fixed_count} 条")

            # 逐条关联需求ID，避免生成的补充用例缺失需求关联
            for c in new_cases:
                if not c.get("req_id"):
                    c["req_id"] = _resolve_req_id(c.get("module"))

            # 通过模块名匹配 RequirementFeature，恢复 feature_id 关联
            from app.models.requirement import RequirementFeature
            _req_ids = set(c.get("req_id") for c in new_cases if c.get("req_id"))
            _module_feat_map = {}
            if _req_ids:
                _feats = db.query(RequirementFeature).filter(
                    RequirementFeature.requirement_id.in_(_req_ids),
                    RequirementFeature.is_deleted == False,
                ).all()
                _module_feat_map = {f.module_name: f.id for f in _feats}
            if _module_feat_map:
                for c in new_cases:
                    if not c.get("feature_id") and c.get("module"):
                        fid = _module_feat_map.get(c["module"])
                        if fid:
                            c["feature_id"] = fid

            created_cases = AICreationService.create_test_cases(
                db,
                project_id=project_id,
                cases=new_cases,
                requirement_id=requirement_id or _resolve_req_id(),
                created_by=opt_task.created_by,
            )

        # 标记评审任务已优化
        review_output = review_task.output_result or {}
        review_output["optimized"] = True
        review_output["optimize_task_id"] = optimize_task_id
        review_output["optimized_at"] = china_now_naive().isoformat()
        review_task.output_result = review_output

        finalize_agent_task(db, opt_task, "success")
        opt_task.output_result = {
            "review_task_id": review_task_id,
            "optimize_mode": optimize_mode,
            "optimized_count": updated_count,
            "created_count": len(created_cases),
            "total_count": updated_count + len(created_cases),
            "requirement_id": requirement_id,
            "module": module_filter,
            "updated_case_ids": updated_case_ids,
            "created_case_ids": [c.id for c in created_cases],
        }
        db.commit()

        logger.info(
            f"评审优化用例完成: review={review_task_id}, "
            f"updated={updated_count}, created={len(created_cases)}"
        )

        return {
            "status": "success",
            "task_id": optimize_task_id,
            "project_id": project_id,
            "created_by": opt_task.created_by,
            "optimize_mode": optimize_mode,
            "total_count": updated_count + len(created_cases),
        }

    def on_success(self, db, result: dict, review_task_id: int, optimize_task_id: int) -> None:
        if result.get("status") != "success":
            return

        # 发送通知
        try:
            opt_task = db.query(AgentTask).filter(AgentTask.id == optimize_task_id).first()
            if not opt_task:
                return
            duration = 0.0
            if opt_task.created_at and opt_task.completed_at:
                duration = round((opt_task.completed_at - opt_task.created_at).total_seconds(), 2)
            notify_event(
                result.get("project_id"),
                "ai.case.generated",
                {
                    "source_name": "评审优化",
                    "strategy": result.get("optimize_mode"),
                    "success_count": result.get("total_count", 0),
                    "failed_count": 0,
                    "duration": duration,
                },
                triggered_by=result.get("created_by"),
            )
        except Exception as notify_e:
            logger.warning(f"发送评审优化通知失败: {notify_e}")

    def on_failure(self, db, error: Exception, review_task_id: int, optimize_task_id: int) -> None:
        logger.error(f"评审优化用例任务失败: {error}", exc_info=True)
        try:
            opt_task = db.query(AgentTask).filter(AgentTask.id == optimize_task_id).first()
            if opt_task:
                finalize_agent_task(db, opt_task, "failed", str(error))
                db.commit()
                notify_ai_task_failed(
                    opt_task.project_id,
                    task_type="评审优化用例",
                    error=str(error),
                    related_object="评审报告优化",
                    triggered_by=opt_task.created_by,
                )
        except Exception:
            pass


@celery_app.task(bind=True, name="review_cases", max_retries=2, queue="ai")
def review_cases_task(self, task_id: int):
    """AI 用例评审任务 — 直接使用 call_with_fallback，不经过 CaseReviewerAgent"""
    return ReviewCasesTask().run(task_id)


@celery_app.task(bind=True, name="optimize_cases_from_review", max_retries=0, queue="ai")
def optimize_cases_from_review_task(
    self,
    review_task_id: int,
    optimize_task_id: int,
):
    """基于评审结果优化/补充用例的异步任务"""
    return OptimizeCasesFromReviewTask().run(review_task_id, optimize_task_id)

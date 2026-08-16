"""
脚本生成器

将 UI 自动化执行记录（execution_log）转换为标准的 Playwright Python 脚本。
支持基于自然语言描述的 AI 脚本生成。
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


SCRIPT_GENERATE_SYSTEM_PROMPT = """你是一个专业的 Playwright 自动化测试脚本生成专家。
请根据用户的测试需求描述，生成完整的、可直接运行的 Playwright Python 异步脚本。

要求：
1. 脚本必须包含 async def run_test() 函数
2. 使用 async_playwright 上下文管理
3. 浏览器使用 chromium，headless=True
4. 视口大小 1280x720
5. 根据描述生成合理的测试步骤，包括：
   - 页面导航 page.goto()
   - 元素点击 page.click()
   - 输入框填写 page.fill()
   - 等待操作 page.wait_for_timeout() / page.wait_for_selector()
   - 截图 page.screenshot()
   - 断言/验证（如需要）
6. 选择器使用常见的 CSS 选择器（id、class、type、placeholder等）
7. 每步添加中文注释
8. 只输出 Python 代码，不要输出解释文字
9. 代码用 ```python 和 ``` 包裹

示例输出：
```python
import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        # 打开登录页面
        await page.goto("https://example.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # 输入用户名
        await page.fill('input[name="username"]', "admin")

        # 不输入密码，直接点击登录
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2000)

        # 截图验证错误提示
        await page.screenshot(path="login_error.png")

        await browser.close()
        print("测试执行完成")

if __name__ == "__main__":
    asyncio.run(run_test())
```
"""


SCRIPT_NAME_SYSTEM_PROMPT = """你是一个测试脚本命名专家。请根据用户的测试需求描述，生成一个简洁、准确、描述性强的脚本名称。

要求：
1. 名称长度控制在 10-50 个字符之间
2. 名称应能体现测试的核心场景或功能
3. 使用中文命名，风格统一
4. 只输出脚本名称本身，不要输出任何解释、引号或其他文字
5. 不要使用"测试脚本"、"自动化脚本"等泛泛之词，要具体

示例：
- 需求：打开登录页，输入用户名admin，不输入密码，点击登录按钮，验证错误提示
- 名称：登录页空密码校验测试

- 需求：在商品搜索框输入"手机"，点击搜索，验证搜索结果列表
- 名称：商品搜索功能验证测试
"""


class ScriptGenerator(BaseAgent):
    """Playwright 脚本生成器（同时保留静态方法供无状态调用）"""

    def run(self, **kwargs) -> Dict[str, Any]:
        """BaseAgent 抽象方法实现"""
        raise NotImplementedError("ScriptGenerator 请使用 generate_with_ai / fix_script_with_ai 等静态方法")

    @staticmethod
    async def generate_script_name(
        description: str,
        target_url: str = "",
        llm_config_id: Optional[int] = None,
        db_session=None,
    ) -> str:
        """
        基于测试需求描述，调用 AI 生成脚本名称

        Args:
            description: 测试需求描述
            target_url: 目标 URL
            llm_config_id: 指定的 LLM 配置ID
            db_session: 数据库会话

        Returns:
            生成的脚本名称
        """
        from app.agents.llm_factory import llm_factory

        user_prompt = f"""请根据以下测试需求生成脚本名称：

目标URL：{target_url or "未指定"}
测试需求：
{description}

请直接输出脚本名称。"""

        messages = [
            SystemMessage(content=SCRIPT_NAME_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
                db_session=db_session,
                messages=messages,
                preferred_config_id=llm_config_id,
                max_retries=2,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            name = ScriptGenerator._clean_script_name(content)
            if not name:
                logger.warning("AI 返回的脚本名称为空，使用默认名称")
                return "AI生成脚本"
            return name
        except Exception as e:
            logger.error(f"AI 生成脚本名称失败: {e}", exc_info=True)
            return "AI生成脚本"

    @staticmethod
    def _clean_script_name(content: str) -> str:
        """清理 AI 返回的脚本名称，去除引号、换行等多余字符"""
        if not content:
            return ""
        name = content.strip()
        # 去除首尾引号
        name = name.strip('"').strip("'").strip("「」").strip("【】")
        # 去除可能的前缀如"名称："
        for prefix in ["名称：", "名称:", "脚本名称：", "脚本名称:", "名字：", "名字:"]:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        # 取第一行
        name = name.split("\n")[0].strip()
        # 限制长度
        if len(name) > 50:
            name = name[:50]
        return name

    @staticmethod
    async def generate_with_ai(
        description: str,
        target_url: str = "",
        script_name: str = "AI生成脚本",
        llm_config_id: Optional[int] = None,
        db_session=None,
        project_id: Optional[int] = None,
    ) -> str:
        """
        基于自然语言描述，调用 AI 生成 Playwright 脚本

        Args:
            description: 测试需求描述
            target_url: 目标 URL
            script_name: 脚本名称
            llm_config_id: 指定的 LLM 配置ID
            db_session: 数据库会话
            project_id: 项目ID（用于 RAG 知识库检索）

        Returns:
            生成的 Python 脚本内容
        """
        from app.agents.llm_factory import llm_factory

        # P2-9: RAG 知识库增强 - 检索项目页面结构和 UI 模式
        rag_context = ""
        if project_id:
            try:
                from app.services.knowledge_base import knowledge_base_service
                docs = knowledge_base_service.search(project_id, f"脚本生成 {description[:200]}", top_k=3)
                if docs:
                    parts = ["以下是从项目知识库中检索到的相关内容，请参考："]
                    for i, doc in enumerate(docs, 1):
                        content = doc.get("content", "") if isinstance(doc, dict) else str(doc)
                        parts.append(f"[{i}] {content}")
                    rag_context = "\n".join(parts)
            except Exception:
                pass

        system_content = SCRIPT_GENERATE_SYSTEM_PROMPT
        if rag_context:
            system_content += f"\n\n{rag_context}"

        user_prompt = f"""请根据以下测试需求生成 Playwright 自动化测试脚本：

脚本名称：{script_name}
目标URL：{target_url or "未指定，请根据描述推断"}
测试需求：
{description}

请生成完整的 Python 脚本。"""

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=user_prompt),
        ]

        try:
            response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
                db_session=db_session,
                messages=messages,
                preferred_config_id=llm_config_id,
                max_retries=2,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            script = ScriptGenerator._extract_python_code(content)

            if not script:
                logger.warning("AI 返回内容中未提取到 Python 代码，使用原始内容")
                script = content

            # 确保脚本包含 run_test 函数
            if "async def run_test()" not in script and "def run_test()" not in script:
                logger.warning("生成的脚本缺少 run_test 函数，包裹到模板中")
                script = ScriptGenerator._wrap_in_template(script, target_url, script_name)

            return script

        except Exception as e:
            logger.error(f"AI 生成脚本失败: {e}", exc_info=True)
            # 失败时返回基础模板
            return ScriptGenerator.generate_template(target_url, script_name)

    @staticmethod
    async def fix_script_with_ai(
        script_content: str,
        error_message: str,
        script_name: str = "脚本修复",
        target_url: str = "",
        llm_config_id: Optional[int] = None,
        db_session=None,
    ) -> str:
        """
        当脚本执行失败时，调用 AI 分析错误并修复脚本

        Args:
            script_content: 原始脚本内容
            error_message: 执行错误信息
            script_name: 脚本名称
            target_url: 目标 URL
            llm_config_id: 指定的 LLM 配置ID
            db_session: 数据库会话

        Returns:
            修复后的 Python 脚本内容
        """
        from app.agents.llm_factory import llm_factory

        fix_system_prompt = """你是一个专业的 Playwright 自动化测试脚本修复专家。
请根据脚本执行时的错误信息，分析问题并修复脚本。

要求：
1. 仔细分析错误原因，定位问题代码
2. 修复选择器、等待逻辑、异常处理等问题
3. 保持脚本的整体结构和测试意图不变
4. 添加必要的等待和异常处理，提高脚本稳定性
5. 修复后的脚本必须包含 async def run_test() 函数
6. 使用 async_playwright 上下文管理
7. 只输出修复后的完整 Python 代码，不要输出解释文字
8. 代码用 ```python 和 ``` 包裹

常见修复方向：
- 选择器不存在：改用更稳定的选择器或添加等待
- 元素不可点击：添加 wait_for_selector 或 scroll_into_view_if_needed
- 页面加载超时：增加超时时间或使用 wait_until="domcontentloaded"
- 断言失败：调整断言逻辑或添加容错
- 导入缺失：补充必要的 import
"""

        user_prompt = f"""脚本名称：{script_name}
目标URL：{target_url or "未指定"}

执行错误信息：
{error_message}

原始脚本内容：
```python
{script_content}
```

请修复上述脚本中的错误，输出完整的修复后脚本。"""

        messages = [
            SystemMessage(content=fix_system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            response, token_usage, used_config_id = await llm_factory.acall_with_fallback(
                db_session=db_session,
                messages=messages,
                preferred_config_id=llm_config_id,
                max_retries=2,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            fixed_script = ScriptGenerator._extract_python_code(content)

            if not fixed_script:
                logger.warning("AI 修复返回内容中未提取到 Python 代码，返回原始脚本")
                return script_content

            # 确保脚本包含 run_test 函数
            if "async def run_test()" not in fixed_script and "def run_test()" not in fixed_script:
                logger.warning("修复后的脚本缺少 run_test 函数，返回原始脚本")
                return script_content

            logger.info(f"AI 修复脚本成功，修复后长度: {len(fixed_script)}")
            return fixed_script

        except Exception as e:
            logger.error(f"AI 修复脚本失败: {e}", exc_info=True)
            # 失败时返回原始脚本
            return script_content

    @staticmethod
    def _extract_python_code(content: str) -> str:
        """从 AI 返回内容中提取 Python 代码"""
        if not content:
            return ""

        # 尝试匹配 ```python ... ```
        pattern = r"```python\s*\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试匹配 ``` ... ```
        pattern = r"```\s*\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 如果没有代码块，检查内容本身是否是 Python 代码
        if "import" in content and ("def " in content or "async def " in content):
            return content.strip()

        return ""

    @staticmethod
    def _wrap_in_template(code: str, target_url: str, name: str) -> str:
        """将代码片段包裹到完整脚本模板中"""
        return f'''"""
{name}
目标URL: {target_url or "https://example.com"}
"""
import asyncio
from playwright.async_api import async_playwright


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={{"width": 1280, "height": 720}})
        page = await context.new_page()

{code}

        await browser.close()
        print("测试执行完成")


if __name__ == "__main__":
    asyncio.run(run_test())
'''

    @staticmethod
    def generate_from_log(
        execution_log: List[Dict[str, Any]],
        target_url: str = "",
        script_name: str = "自动生成脚本",
        case_title: str = "",
    ) -> str:
        """
        根据执行日志生成 Playwright 脚本

        Args:
            execution_log: 执行日志列表，每项包含 action/action_input/status/observation
            target_url: 目标 URL
            script_name: 脚本名称
            case_title: 关联用例标题

        Returns:
            生成的 Python 脚本内容
        """
        steps = []
        imports = set(["asyncio", "from playwright.async_api import async_playwright"])

        # 过滤出有效的操作步骤
        valid_actions = [
            "navigate_browser", "click_element", "fill_input",
            "get_elements", "extract_text", "extract_hyperlinks",
            "current_webpage", "previous_webpage", "take_screenshot",
            "wait_for_selector", "press_key", "scroll_page",
        ]

        for idx, log in enumerate(execution_log):
            action = log.get("action", "")
            if action not in valid_actions:
                continue
            if log.get("status") != "success" and action != "navigate_browser":
                continue

            action_input = log.get("action_input") or log.get("params", {})
            if isinstance(action_input, str):
                try:
                    action_input = json.loads(action_input)
                except Exception:
                    action_input = {}

            step_code = ScriptGenerator._convert_action(action, action_input, idx + 1)
            if step_code:
                steps.append(step_code)

        # 如果没有有效步骤，生成一个基础模板
        if not steps:
            steps.append(f'        await page.goto("{target_url or "https://example.com"}", wait_until="domcontentloaded")')
            steps.append("        await page.wait_for_timeout(2000)")

        # 组装脚本
        script = f'''"""
{script_name}
关联用例: {case_title or "无"}
目标URL: {target_url or "无"}
自动生成时间: 由 AITS 平台生成
"""
import asyncio
from playwright.async_api import async_playwright


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={{"width": 1280, "height": 720}})
        page = await context.new_page()

{chr(10).join(steps)}

        await browser.close()
        print("测试执行完成")


if __name__ == "__main__":
    asyncio.run(run_test())
'''
        return script

    @staticmethod
    def _convert_action(action: str, params: Dict[str, Any], step_num: int) -> Optional[str]:
        """将单个操作转换为 Playwright 代码"""
        selector = params.get("selector", "")
        url = params.get("url", "")
        text = params.get("text", "")
        key = params.get("key", "")
        description = params.get("description", "")

        comment = f"        # 步骤{step_num}: {description or action}"

        if action == "navigate_browser":
            return f'{comment}\n        await page.goto("{url}", wait_until="domcontentloaded")\n        await page.wait_for_timeout(1000)'

        elif action == "click_element":
            sel = selector or "button"
            return f'{comment}\n        await page.click("{sel}", timeout=5000)\n        await page.wait_for_timeout(500)'

        elif action == "fill_input":
            sel = selector or "input"
            return f'{comment}\n        await page.fill("{sel}", "{text}")'

        elif action == "press_key":
            sel = selector or "body"
            return f'{comment}\n        await page.press("{sel}", "{key}")'

        elif action == "wait_for_selector":
            sel = selector or "body"
            return f'{comment}\n        await page.wait_for_selector("{sel}", timeout=10000)'

        elif action == "take_screenshot":
            return f'{comment}\n        await page.screenshot(path="screenshot_{step_num}.png")'

        elif action == "previous_webpage":
            return f'{comment}\n        await page.go_back()\n        await page.wait_for_timeout(500)'

        elif action == "scroll_page":
            direction = params.get("direction", "down")
            if direction == "down":
                return f'{comment}\n        await page.evaluate("window.scrollBy(0, 500)")'
            else:
                return f'{comment}\n        await page.evaluate("window.scrollBy(0, -500)")'

        elif action == "extract_text":
            sel = selector or "body"
            return f'{comment}\n        text = await page.text_content("{sel}")\n        print("提取文本:", text[:100])'

        elif action == "current_webpage":
            return f'{comment}\n        print("当前URL:", page.url)\n        print("页面标题:", await page.title())'

        elif action == "get_elements":
            sel = selector or "*"
            return f'{comment}\n        elements = await page.query_selector_all("{sel}")\n        print(f"找到 {{len(elements)}} 个元素")'

        elif action == "extract_hyperlinks":
            return f'{comment}\n        links = await page.eval_on_selector_all("a", "elements => elements.map(e => ({{text: e.innerText, href: e.href}}))")\n        print("找到链接:", len(links))'

        return None

    @staticmethod
    def generate_template(target_url: str = "", name: str = "新建脚本") -> str:
        """生成空白脚本模板"""
        return f'''"""
{name}
目标URL: {target_url or "https://example.com"}
"""
import asyncio
from playwright.async_api import async_playwright


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={{"width": 1280, "height": 720}})
        page = await context.new_page()

        # 在此编写测试步骤
        await page.goto("{target_url or "https://example.com"}")
        await page.wait_for_timeout(2000)

        await browser.close()
        print("测试执行完成")


if __name__ == "__main__":
    asyncio.run(run_test())
'''

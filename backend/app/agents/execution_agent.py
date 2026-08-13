"""
UI 自动化执行 Agent

基于 Playwright，通过自然语言指令驱动浏览器执行测试。
支持 SSE 流式输出执行过程。
"""
import asyncio
import base64
import json
import logging
import os
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from playwright.async_api import async_playwright, Browser, Page
from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)

# 浏览器工具定义
BROWSER_TOOLS = [
    {
        "name": "navigate_browser",
        "description": "导航到指定 URL",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标网址"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "click_element",
        "description": "点击页面上的元素",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器或元素文本"},
                "description": {"type": "string", "description": "元素描述"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "fill_input",
        "description": "在输入框中填写文本",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器"},
                "text": {"type": "string", "description": "要输入的文本"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "get_elements",
        "description": "获取页面元素信息（用于了解页面结构）",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器，留空获取所有可交互元素"}
            }
        }
    },
    {
        "name": "extract_text",
        "description": "提取页面文本内容",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器，留空提取整个页面"}
            }
        }
    },
    {
        "name": "extract_hyperlinks",
        "description": "提取页面所有链接",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "current_webpage",
        "description": "获取当前页面 URL 和标题",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "previous_webpage",
        "description": "浏览器后退",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "take_screenshot",
        "description": "截取当前页面截图",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "finish",
        "description": "完成任务，总结执行结果",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "执行结果总结"},
                "status": {"type": "string", "description": "passed/failed", "enum": ["passed", "failed"]}
            },
            "required": ["result", "status"]
        }
    }
]

EXECUTION_SYSTEM_PROMPT = """你是一个专业的 UI 自动化测试工程师。你的任务是通过操作浏览器来完成用户指定的测试任务。

## 你的能力
你可以使用以下浏览器工具：
{tools_description}

## 工作原则
1. 先观察页面结构（get_elements / extract_text），再进行操作
2. 每一步操作前，明确你要做什么以及为什么
3. 如果操作失败，尝试其他方式（换选择器、等待页面加载等）
4. 最多执行 20 步操作，避免无限循环
5. 完成任务后调用 finish 工具总结结果
6. 如果遇到无法解决的问题，调用 finish 并标记 failed

## 输出格式
每一步输出 JSON：
{{
    "thought": "你的思考过程",
    "action": "工具名称",
    "action_input": {{...工具参数...}}
}}
"""


class ExecutionAgent:
    """UI 自动化执行 Agent"""

    def __init__(self, db_session=None, llm_config_id: Optional[int] = None):
        self.db = db_session
        self.llm_config_id = llm_config_id
        self.execution_log: List[Dict[str, Any]] = []
        self.screenshot_path: str = ""
        self._step_start_time: float = 0  # 当前步骤开始时间

    async def execute(
        self,
        instruction: str,
        target_url: str = "",
        headless: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行 UI 自动化测试，流式输出每一步

        Args:
            instruction: 自然语言测试指令
            target_url: 起始 URL
            headless: 是否无头模式
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        start_time = time.time()
        step_count = 0
        max_steps = 20
        max_duration = 300  # 最大执行时长 5 分钟
        error_message = ""

        # 启动浏览器
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            try:
                # 构建初始消息
                tools_desc = json.dumps(BROWSER_TOOLS, ensure_ascii=False, indent=2)
                messages = [
                    SystemMessage(content=EXECUTION_SYSTEM_PROMPT.format(tools_description=tools_desc)),
                    HumanMessage(content=f"测试任务：{instruction}\n\n起始 URL：{target_url}\n\n请开始执行。"),
                ]

                # 如果有起始 URL，先导航
                if target_url:
                    self._step_start_time = time.time()
                    yield {"type": "step", "step": step_count, "action": "navigate", "detail": f"导航到 {target_url}"}
                    try:
                        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as nav_e:
                        error_message = f"页面导航失败: {str(nav_e)}"
                        yield {"type": "step", "step": step_count, "action": "navigate_error", "detail": error_message}
                        yield {"type": "finish", "status": "failed", "result": error_message}
                        step_count += 1
                        self._log_step("navigate_browser", {"url": target_url}, "failed", error_message, time.time() - self._step_start_time)
                        return
                    await page.wait_for_timeout(1000)
                    step_count += 1
                    self._log_step("navigate_browser", {"url": target_url}, "success", "")
                    self._step_start_time = time.time()  # 为下一步设置起始时间

                # Agent 循环
                while step_count < max_steps:
                    # 检查整体超时
                    if time.time() - start_time > max_duration:
                        error_message = f"执行超时（超过 {max_duration} 秒），任务终止"
                        yield {"type": "finish", "status": "failed", "result": error_message}
                        self._log_step("timeout", {}, "failed", error_message, time.time() - self._step_start_time if self._step_start_time else 0)
                        break

                    # 调用 LLM 获取下一步动作
                    try:
                        llm, _ = llm_factory.get_llm_with_fallback(
                            self.db, preferred_config_id=self.llm_config_id
                        )
                        response = llm.invoke(messages)
                    except Exception as llm_e:
                        error_message = f"大模型调用失败: {str(llm_e)}"
                        yield {"type": "step", "step": step_count, "action": "llm_error", "detail": error_message}
                        yield {"type": "finish", "status": "failed", "result": error_message}
                        self._log_step("llm_invoke", {}, "failed", error_message, time.time() - self._step_start_time if self._step_start_time else 0)
                        break

                    messages.append(AIMessage(content=response.content))

                    # 解析动作
                    action_data = self._parse_action(response.content)
                    if not action_data:
                        yield {"type": "step", "step": step_count, "action": "parse_error", "detail": "无法解析 AI 输出，重试"}
                        messages.append(HumanMessage(content="请严格按照 JSON 格式输出你的下一步动作。"))
                        step_count += 1
                        continue

                    action = action_data.get("action", "")
                    action_input = action_data.get("action_input", {})
                    thought = action_data.get("thought", "")

                    yield {
                        "type": "step",
                        "step": step_count,
                        "action": action,
                        "thought": thought,
                        "detail": json.dumps(action_input, ensure_ascii=False)
                    }

                    # 执行动作
                    action_start_time = time.time()
                    if action == "finish":
                        result = action_input.get("result", "")
                        status = action_input.get("status", "passed")
                        self._log_step(action, action_input, status, result, time.time() - action_start_time)
                        yield {"type": "finish", "status": status, "result": result}
                        break

                    try:
                        observation = await self._execute_tool(page, action, action_input)
                    except Exception as tool_e:
                        error_message = f"工具执行失败（{action}）: {str(tool_e)}"
                        yield {"type": "step", "step": step_count, "action": "tool_error", "detail": error_message}
                        yield {"type": "finish", "status": "failed", "result": error_message}
                        self._log_step(action, action_input, "failed", error_message, time.time() - action_start_time)
                        break

                    step_duration = time.time() - action_start_time
                    self._log_step(action, action_input, "success", observation[:200], step_duration)

                    # 截图
                    if action in ("click_element", "fill_input", "navigate_browser"):
                        try:
                            screenshot = await page.screenshot()
                            self.screenshot_path = f"/tmp/execution_{int(time.time())}.png"
                            with open(self.screenshot_path, "wb") as f:
                                f.write(screenshot)
                        except Exception:
                            pass

                    # 将观察结果反馈给 LLM
                    messages.append(HumanMessage(content=f"执行结果：\n{observation}"))
                    step_count += 1

                else:
                    error_message = "达到最大步数限制（20步），任务未完成"
                    yield {"type": "finish", "status": "failed", "result": error_message}
                    self._log_step("max_steps", {}, "failed", error_message, time.time() - self._step_start_time if self._step_start_time else 0)

            except Exception as e:
                error_message = f"执行异常: {str(e)}"
                logger.error(f"执行异常: {e}")
                yield {"type": "error", "message": error_message}
                yield {"type": "finish", "status": "failed", "result": error_message}
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

        duration = time.time() - start_time
        # 将截图转为 base64 供前端展示
        screenshot_base64 = ""
        if self.screenshot_path and os.path.exists(self.screenshot_path):
            try:
                with open(self.screenshot_path, "rb") as f:
                    screenshot_base64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        yield {
            "type": "complete",
            "duration": round(duration, 2),
            "steps": len(self.execution_log),
            "screenshot": self.screenshot_path,
            "screenshot_base64": screenshot_base64,
        }

    def _parse_action(self, content: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 输出的动作 JSON"""
        import re
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return None

    async def _execute_tool(self, page: Page, action: str, params: Dict[str, Any]) -> str:
        """执行浏览器工具，返回观察结果"""
        try:
            if action == "navigate_browser":
                url = params.get("url", "")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(500)
                return f"已导航到 {url}，页面标题: {await page.title()}"

            elif action == "click_element":
                selector = params.get("selector", "")
                try:
                    await page.click(selector, timeout=5000)
                except Exception:
                    # 尝试按文本点击
                    await page.get_by_text(selector).click(timeout=5000)
                await page.wait_for_timeout(500)
                return f"已点击元素: {selector}"

            elif action == "fill_input":
                selector = params.get("selector", "")
                text = params.get("text", "")
                await page.fill(selector, text)
                return f"已在 {selector} 中输入: {text}"

            elif action == "get_elements":
                selector = params.get("selector", "")
                if selector:
                    elements = await page.query_selector_all(selector)
                    info = [await e.inner_text() for e in elements[:10]]
                    return f"找到 {len(elements)} 个元素: {info}"
                else:
                    # 获取所有可交互元素
                    buttons = await page.query_selector_all("button, a, input, select, textarea")
                    info = []
                    for b in buttons[:20]:
                        tag = await b.evaluate("el => el.tagName")
                        text = await b.inner_text()
                        placeholder = await b.get_attribute("placeholder") or ""
                        info.append(f"<{tag}> {text[:30]} {placeholder[:20]}")
                    return f"页面可交互元素 ({len(buttons)}个):\n" + "\n".join(info)

            elif action == "extract_text":
                selector = params.get("selector", "")
                if selector:
                    text = await page.inner_text(selector)
                else:
                    text = await page.inner_text("body")
                return f"页面文本（前1000字）:\n{text[:1000]}"

            elif action == "extract_hyperlinks":
                links = await page.query_selector_all("a")
                result = []
                for link in links[:20]:
                    href = await link.get_attribute("href") or ""
                    text = await link.inner_text()
                    result.append(f"{text[:30]} -> {href}")
                return f"页面链接 ({len(links)}个):\n" + "\n".join(result)

            elif action == "current_webpage":
                return f"当前 URL: {page.url}\n标题: {await page.title()}"

            elif action == "previous_webpage":
                await page.go_back()
                return f"已后退，当前 URL: {page.url}"

            elif action == "take_screenshot":
                screenshot = await page.screenshot()
                path = f"/tmp/screenshot_{int(time.time())}.png"
                with open(path, "wb") as f:
                    f.write(screenshot)
                return f"截图已保存: {path}"

            else:
                return f"未知工具: {action}"

        except Exception as e:
            return f"执行失败: {str(e)}"

    def _log_step(self, action: str, params: Dict, status: str, observation: str, duration: float = 0):
        """记录执行步骤"""
        self.execution_log.append({
            "timestamp": time.time(),
            "action": action,
            "params": params,
            "status": status,
            "observation": observation,
            "duration": round(duration, 3),
        })

    def get_execution_log(self) -> List[Dict[str, Any]]:
        return self.execution_log

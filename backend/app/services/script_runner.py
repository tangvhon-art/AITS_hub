"""
脚本执行统一服务
提供脚本执行 + AI 自动修复重试的公共逻辑，供 Celery 任务和 BackgroundTasks 降级复用
"""
import asyncio
import json
import time
import re
import sys
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.test_run import TestRun
from app.models.automation_script import AutomationScript
from app.models.agent_task import AgentTask
from app.agents.script_generator import ScriptGenerator
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


def apply_headless_mode(script_content: str, headless: bool = True) -> str:
    """根据 headless 参数调整脚本中的浏览器启动配置"""
    if not script_content:
        return script_content
    content = re.sub(
        r'(\w+\s*=\s*await\s+\w+\.chromium\.launch\s*\(\s*headless\s*=\s*)\w+',
        rf'\g<1>{headless}',
        script_content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r'(\w+\s*=\s*await\s+\w+\.chromium\.launch\s*\()(?!.*headless)',
        rf'\g<1>headless={headless}, ',
        content,
    )
    return content


def apply_params(content: str, params: Optional[dict]) -> str:
    """脚本参数替换，将 {{key}} 替换为实际值"""
    if params:
        for key, value in params.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


# ---------------------------------------------------------------------------
# 智能定位兼容层
# 生成脚本可能存在将「元素文本描述」直接当作 selector 使用的情况，
# 例如 page.fill("邮箱/用户名/任意门LDAP账号", "...") / page.click("登录")。
# 此类描述不是合法 CSS selector，playwright 解析会报 Unexpected token。
# 执行前将 page.fill/click/type 改写为 _sm_* 智能定位 helper，
# 描述型参数自动回退到 placeholder/label/role/text 等语义定位。
# ---------------------------------------------------------------------------

_SM_ACTION_MAP = {"fill": "fill", "click": "click", "type": "type"}


def _looks_like_text_desc(s: str) -> bool:
    """判断 selector 是否为「文本描述」而非合法 CSS selector"""
    if not s:
        return False
    # 含非 ASCII（中文等）→ 判定为元素描述
    if any(ord(c) > 127 for c in s):
        return True
    # 含 CSS 非法字符 / ( ) 等 → 判定为元素描述
    if any(ch in s for ch in ("/", "(", ")", "；", "：", "，", "（", "）")):
        return True
    return False


def _make_locators(frame, desc: str, for_click: bool):
    """构造语义定位候选列表（惰性，逐个 count 校验）"""
    if for_click:
        return [
            lambda: frame.get_by_role("button", name=desc, exact=True),
            lambda: frame.get_by_role("link", name=desc, exact=True),
            lambda: frame.get_by_text(desc, exact=True),
            lambda: frame.get_by_placeholder(desc),
            lambda: frame.get_by_label(desc),
            lambda: frame.locator(f"text={desc}"),
        ]
    return [
        lambda: frame.get_by_placeholder(desc),
        lambda: frame.get_by_label(desc),
        lambda: frame.get_by_role("textbox", name=desc),
        lambda: frame.locator(f'input[placeholder*="{desc}"]'),
        lambda: frame.locator(f'textarea[placeholder*="{desc}"]'),
        lambda: frame.get_by_text(desc, exact=False),
        lambda: frame.locator(f"text={desc}"),
    ]


async def _try_locate_in_frame(frame, desc: str, for_click: bool = False):
    """在单个 frame 内用语义定位候选逐一尝试，返回 locator 或 None"""
    for make in _make_locators(frame, desc, for_click):
        try:
            loc = make()
            n = await loc.count()
            if n > 0:
                return loc.first if n > 1 else loc
        except Exception:
            continue
    return None


# SSO 登录页默认是「Lark/飞书登录」tab，账号输入框需切换「账号登录」tab 后才出现。
# 当定位不到登录输入类元素时，自动点击这些 tab 再重试。
_LOGIN_TAB_TEXTS = [
    "Account Login", "账号登录", "密码登录", "用户名登录",
    "账户登录", "邮箱登录", "账号密码登录",
]


def _is_login_input_desc(desc: str) -> bool:
    """是否为登录输入类描述（用户名/账号/邮箱/LDAP/密码）"""
    return any(k in desc for k in ("用户名", "账号", "账户", "邮箱", "LDAP", "密码"))


async def _try_click_login_tab(page):
    """尝试点击登录 tab（Account Login / 账号登录 等），返回是否点击成功"""
    for txt in _LOGIN_TAB_TEXTS:
        try:
            el = page.get_by_text(txt, exact=False)
            n = await el.count()
            if n == 0:
                continue
            try:
                await el.first.click(timeout=2500)
            except Exception:
                try:
                    await el.first.click(force=True, timeout=2500)
                except Exception:
                    continue
            await page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


def _norm_text(s: str) -> str:
    return "".join(str(s).split())


# 登录表单中英关键词映射：描述是中文（如「邮箱/用户名/任意门LDAP账号」「密码」），
# 而页面 placeholder 是英文（如 Email/Username/LDAP Account / Password）。
_LOGIN_FIELD_HINTS = {
    "user": ["用户名", "账号", "账户", "邮箱", "LDAP", "username", "account", "email", "ldap", "user", "手机", "mobile"],
    "pwd": ["密码", "password", "pwd", "pass"],
}


def _login_field_kind(desc: str):
    dl = desc.lower()
    for kind, kws in _LOGIN_FIELD_HINTS.items():
        if any(k.lower() in dl for k in kws):
            return kind
    return None


async def _try_login_form_match(page, desc: str):
    """登录表单启发式：按描述关键词类型匹配可见输入框（中英映射）"""
    kind = _login_field_kind(desc)
    if kind is None:
        return None
    for frame in page.frames:
        try:
            items = await frame.locator("input:visible").evaluate_all(
                "els => els.map((e, i) => ({i: i, ph: (e.placeholder || '').toLowerCase(), "
                "tp: e.type, name: (e.name || '').toLowerCase(), id: (e.id || '').toLowerCase()}))"
            )
            for it in items:
                blob = f"{it.get('ph') or ''} {it.get('name') or ''} {it.get('id') or ''}"
                if kind == "pwd":
                    if "password" in blob or "pwd" in blob:
                        return frame.locator("input:visible").nth(it["i"])
                else:
                    # user 类：排除密码框，placeholder/name/id 含登录用户名关键词
                    if "password" in blob or "pwd" in blob:
                        continue
                    if any(k in blob for k in ("email", "username", "account", "ldap", "user", "mobile", "phone")):
                        return frame.locator("input:visible").nth(it["i"])
        except Exception:
            continue
    return None


async def _try_login_button(page, desc: str):
    """登录按钮启发式：描述含「登录/login」时匹配按钮文本（中英映射，排除飞书/Lark 长文案）"""
    dl = desc.lower()
    if not ("登录" in dl or "login" in dl or "sign" in dl):
        return None
    for frame in page.frames:
        try:
            btns = frame.locator("button, [role=button]")
            n = await btns.count()
            for i in range(n):
                try:
                    t = (await btns.nth(i).inner_text(timeout=800)).strip()
                except Exception:
                    continue
                # 排除「飞书一键登录」这类营销长文案按钮
                if "飞书" in t or "一键" in t or "lark" in t.lower():
                    continue
                tl = t.lower()
                if tl in ("login", "log in", "sign in", "signin", "登录", "登 录", "立即登录"):
                    return btns.nth(i)
                # 宽松：归一化后与描述完全一致
                if _norm_text(t) == _norm_text(desc):
                    return btns.nth(i)
        except Exception:
            continue
    return None


async def _try_fuzzy_placeholder(page, desc: str):
    """兜底：扫描所有 frame 的 input/textarea，placeholder/aria-label 归一化后模糊匹配"""
    nd = _norm_text(desc)
    if not nd:
        return None
    for frame in page.frames:
        try:
            info = await frame.locator("input, textarea").evaluate_all(
                "els => els.map((e, i) => ({i: i, ph: e.placeholder || '', aria: e.getAttribute('aria-label') || ''}))"
            )
            for it in info:
                cand = _norm_text(f"{it.get('ph') or ''}|{it.get('aria') or ''}")
                if cand and (nd in cand or cand in nd):
                    return frame.locator("input, textarea").nth(it["i"])
        except Exception:
            continue
    return None


async def _locate_once(page, desc: str, for_click: bool = False):
    """单轮智能定位：登录按钮优先 → 主 frame → 多 frame → 登录 tab 切换 → 登录表单启发式 → placeholder 模糊匹配"""
    # 0) 登录按钮场景：先精确匹配提交按钮（避免子串命中「飞书一键登录」等长文案）
    if for_click:
        dl = desc.lower()
        if "登录" in dl or "login" in dl or "sign" in dl:
            loc = await _try_login_button(page, desc)
            if loc is not None:
                return loc
    # 1) 主 frame
    loc = await _try_locate_in_frame(page.main_frame, desc, for_click)
    if loc is not None:
        return loc
    # 2) 其他 frame（iframe 内嵌登录表单等）
    for frame in page.frames:
        if frame is page.main_frame:
            continue
        loc = await _try_locate_in_frame(frame, desc, for_click)
        if loc is not None:
            return loc
    # 3) 登录页场景：默认 Lark tab，账号输入框需切换 tab 后才出现
    if not for_click and _is_login_input_desc(desc):
        if await _try_click_login_tab(page):
            loc = await _try_locate_in_frame(page.main_frame, desc, for_click)
            if loc is not None:
                return loc
            for frame in page.frames:
                if frame is page.main_frame:
                    continue
                loc = await _try_locate_in_frame(frame, desc, for_click)
                if loc is not None:
                    return loc
    # 4) 登录表单启发式（中英关键词映射）
    if not for_click:
        loc = await _try_login_form_match(page, desc)
    else:
        loc = await _try_login_button(page, desc)
    if loc is not None:
        return loc
    # 5) 兜底：placeholder/aria 归一化模糊匹配
    return await _try_fuzzy_placeholder(page, desc)


async def _smart_locate(page, desc: str, for_click: bool = False):
    """智能定位（带等待重试）：页面重定向/懒加载时登录表单可能未渲染，轮询重试"""
    for attempt in range(5):
        loc = await _locate_once(page, desc, for_click)
        if loc is not None:
            return loc
        if attempt < 4:
            await page.wait_for_timeout(2000)
    return None


async def _sm_fill(page, selector, value, **kwargs):
    if _looks_like_text_desc(selector):
        loc = await _smart_locate(page, selector, for_click=False)
        if loc is not None:
            await loc.fill(value, **kwargs)
            return
        # 不再把文本描述当 CSS selector 回退（否则报 Unexpected token），改为明确报错
        raise RuntimeError(f"无法定位到元素: {selector}（已尝试 placeholder/label/text 等语义定位）")
    await page.fill(selector, value, **kwargs)


async def _sm_click(page, selector, **kwargs):
    if _looks_like_text_desc(selector):
        loc = await _smart_locate(page, selector, for_click=True)
        if loc is not None:
            await loc.click(**kwargs)
            return
        raise RuntimeError(f"无法定位到元素: {selector}（已尝试 button/link/text 等语义定位）")
    await page.click(selector, **kwargs)


async def _sm_type(page, selector, value, **kwargs):
    if _looks_like_text_desc(selector):
        loc = await _smart_locate(page, selector, for_click=False)
        if loc is not None:
            await loc.type(value, **kwargs)
            return
        raise RuntimeError(f"无法定位到元素: {selector}（已尝试 placeholder/label/text 等语义定位）")
    await page.type(selector, value, **kwargs)


def apply_selector_compat(content: str) -> str:
    """改写脚本：page.fill/click/type -> _sm_*（智能定位）"""
    return re.sub(
        r"\bpage\.(fill|click|type)\s*\(",
        lambda m: f"_sm_{m.group(1)}(page, ",
        content,
    )


_SM_HELPERS = {"_sm_fill": _sm_fill, "_sm_click": _sm_click, "_sm_type": _sm_type}

# ============ 步骤日志注入：把脚本中 '# 步骤N: xxx' 注释转为执行日志 ============

_STEP_LOG_INJECT = '''
# 兼容层：selector 智能定位 + navigation 容错（子进程执行时自动 import）
try:
    from app.services.script_runner import _sm_fill, _sm_click, _sm_type, _install_nav_retry
    _install_nav_retry()
except Exception:
    pass

__step_logs = []
def __log_step(detail):
    import time as _step_t
    __step_logs.append({"action": "step", "detail": detail, "timestamp": _step_t.time(), "status": "info"})
import sys as _step_sys
_step_orig_print = print
def __log_print(*args, **kwargs):
    try:
        _step_orig_print(*args, **kwargs)
    except Exception:
        pass
    try:
        sep = kwargs.get("sep", " ")
        msg = sep.join(str(a) for a in args)
        if msg:
            import time as _step_t2
            __step_logs.append({"action": "print", "detail": msg, "timestamp": _step_t2.time(), "status": "info"})
    except Exception:
        pass
print = __log_print
# 子进程退出时把步骤日志以 JSON 标记输出到 stderr，供主进程解析
import atexit as _step_atexit
def _step_dump_logs():
    try:
        import json as _step_json
        _step_sys.stderr.write("__STEP_LOGS__:" + _step_json.dumps(__step_logs, ensure_ascii=False) + "\\n")
        _step_sys.stderr.flush()
    except Exception:
        pass
_step_atexit.register(_step_dump_logs)
'''

# 最近一次执行的步骤日志（run_script_sync 执行后设置，调用方可读取）
_last_step_logs = []


def get_last_step_logs() -> list:
    """获取最近一次脚本执行收集到的步骤日志"""
    return list(_last_step_logs)


def _inject_step_logging(content: str) -> str:
    """
    把脚本中的 '# 步骤N: xxx' 注释转换为 __log_step('步骤N: xxx') 调用，
    并在脚本顶部注入 __step_logs 列表和 __log_step 函数。
    执行后可从 local_vars['__step_logs'] 读取所有步骤日志。
    """
    def _replace(m):
        indent = m.group(1)
        text = m.group(2).strip()
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'{indent}__log_step("{escaped}")'

    content = re.sub(
        r'^(\s*)#\s*(步骤\s*\d+\s*[:：][^\n]*)$',
        _replace,
        content,
        flags=re.MULTILINE,
    )
    return _STEP_LOG_INJECT + "\n" + content


_NAV_RETRY_MARKERS = ("Execution context was destroyed",)


def _install_nav_retry():
    """navigation 容错：monkey-patch Page 关键 async 方法。

    登录/跳转等 navigation 期间调用页面方法会报
    "Execution context was destroyed, most likely because of a navigation"。
    这里对常用方法做「等待页面稳定后重试」，保证脚本在页面跳转后仍能完整运行。
    """
    try:
        from playwright.async_api import Page as AsyncPage
    except Exception:
        return
    if getattr(AsyncPage, "_nav_retry_installed", False):
        return

    async def _retry_call(orig_m, self, args, kwargs):
        for attempt in range(4):
            try:
                return await orig_m(self, *args, **kwargs)
            except Exception as e:
                if any(m in str(e) for m in _NAV_RETRY_MARKERS):
                    await asyncio.sleep(1.2)
                    continue
                raise
        # 最后再尝试一次原方法（让原始错误上抛给调用方）
        return await orig_m(self, *args, **kwargs)

    # 仅 patch async 方法（同步方法如 locator() 不可包成 async，会破坏 API 契约）
    for name in (
        "query_selector_all", "text_content", "inner_text", "inner_html",
        "evaluate", "fill", "click", "type", "screenshot",
        "wait_for_selector", "content", "get_attribute",
    ):
        orig = getattr(AsyncPage, name, None)
        if orig is None:
            continue

        async def wrapper(self, *args, _orig=orig, **kwargs):
            return await _retry_call(_orig, self, args, kwargs)

        wrapper.__name__ = name
        wrapper._nav_retry_wrapped = True
        setattr(AsyncPage, name, wrapper)
    setattr(AsyncPage, "_nav_retry_installed", True)


def _run_in_real_thread(coro_factory, *args, **kwargs):
    """在真正独立的 OS 线程 + 全新事件循环中执行协程工厂，规避 asyncio 事件循环冲突。

    背景：Celery worker 在 macOS 上使用 eventlet 协程池（-P eventlet）。
    eventlet monkey-patch 会把 threading.Thread / ThreadPoolExecutor / asyncio.to_thread
    全部变成 greenlet，挤在同一 OS 线程上执行——于是脚本执行链上的
    asyncio.run() 会检测到「当前线程已有 running event loop」而报错：
        asyncio.run() cannot be called from a running event loop
    这里用 eventlet.patcher.original('threading').Thread 创建真实的 OS 线程，
    在线程内 new_event_loop + run_until_complete 执行协程，彻底避开冲突。
    """
    try:
        import eventlet.patcher
        ThreadCls = eventlet.patcher.original("threading").Thread
    except Exception:
        import threading
        ThreadCls = threading.Thread

    result = {}

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result["value"] = loop.run_until_complete(coro_factory(*args, **kwargs))
        except BaseException as e:  # noqa: BLE001
            result["error"] = e
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    t = ThreadCls(target=_target, daemon=True)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def run_script_sync(content: str, script_id: int, project_id: int = None, run_id: int = None) -> tuple[bool, str]:
    """
    同步执行脚本（子进程隔离，彻底避开 eventlet monkey-patch 导致的 event loop 冲突）

    根治方案：将脚本写入临时文件，用干净的 Python 子进程执行。
    子进程无 eventlet patch，asyncio.run() 和 playwright async API 完全正常。
    步骤日志通过 stderr 的 __STEP_LOGS__ 标记回传主进程。

    返回 (是否成功, 错误信息)
    """
    import subprocess
    import tempfile
    import os
    import json

    tmp_path = None
    try:
        # 执行前清理旧截图
        try:
            from app.tasks.cleanup_tasks import cleanup_uploads
            cleanup_uploads()
        except Exception:
            pass

        # 安装 UI 自愈包装器（主进程 monkey-patch，子进程通过注入代码 import 兼容层）
        if project_id:
            try:
                from app.services.ui_healing.healing_wrapper import install_healing_wrapper
                from app.database import SessionLocal
                install_healing_wrapper(
                    db_session_factory=SessionLocal,
                    project_id=project_id,
                    script_id=script_id,
                    run_id=run_id,
                    enabled=True,
                )
            except Exception as e:
                logger.warning(f"自愈包装器安装失败（不影响执行）: {e}")

        # 兼容元素描述型 selector：page.fill/click/type -> _sm_* 智能定位
        try:
            content = apply_selector_compat(content)
        except Exception as e:
            logger.warning(f"selector 兼容改写失败（继续原样执行）: {e}")

        # 步骤日志注入：把 '# 步骤N: xxx' 注释转为 __log_step 调用，并重写 print
        try:
            content = _inject_step_logging(content)
        except Exception as e:
            logger.warning(f"步骤日志注入失败（继续原样执行）: {e}")

        # 兜底：如果脚本没有显式的 asyncio.run 调用，在末尾追加 __main__ 执行块
        if "asyncio.run(" not in content:
            content += '\nif __name__ == "__main__":\n    import asyncio as _a\n    if "run_test" in dir():\n        _a.run(run_test())\n'

        # 写入临时文件
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix=f"aits_script_{script_id}_")
        with os.fdopen(tmp_fd, "w") as f:
            f.write(content)

        # 子进程执行：cwd 设为 backend 目录，确保 app.* 模块可 import
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 用 venv python 绝对路径，避免 sys.executable 在 venv symlink/eventlet 下解析到系统 python
        venv_python = os.path.join(backend_dir, "venv", "bin", "python")
        if not os.path.exists(venv_python):
            venv_python = sys.executable
        # 设置 PYTHONPATH，确保子进程能 import app.* 模块（脚本在 /tmp，cwd 不会自动入 sys.path）
        sub_env = os.environ.copy()
        sub_env["PYTHONPATH"] = backend_dir + os.pathsep + sub_env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [venv_python, tmp_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=backend_dir,
            env=sub_env,
        )

        # 解析 stderr 中的步骤日志（子进程 atexit 时输出 __STEP_LOGS__:{json}）
        step_logs = []
        stderr_lines = proc.stderr.splitlines()
        for line in stderr_lines:
            if line.startswith("__STEP_LOGS__:"):
                try:
                    step_logs = json.loads(line[len("__STEP_LOGS__:"):])
                except Exception:
                    pass

        global _last_step_logs
        _last_step_logs = step_logs

        if proc.returncode != 0:
            # 提取错误信息（排除 __STEP_LOGS__ 标记行，取最后 30 行）
            error_lines = [l for l in stderr_lines if not l.startswith("__STEP_LOGS__:")]
            error_msg = "\n".join(error_lines[-30:]) if error_lines else proc.stdout[-1000:]
            return False, error_msg[:2000]
        return True, ""
    except subprocess.TimeoutExpired:
        try:
            _last_step_logs = []
        except Exception:
            pass
        return False, f"脚本执行超时（300秒）"
    except Exception as e:
        try:
            _last_step_logs = []
        except Exception:
            pass
        return False, str(e)
    finally:
        # 清理临时文件
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        # 聚合页面知识库（异步，不阻塞）
        if project_id:
            try:
                from app.tasks.ui_healing_tasks import aggregate_page_knowledge
                aggregate_page_knowledge.delay(project_id)
            except Exception:
                pass


async def execute_script_async(content: str, script_id: int, project_id: int = None, run_id: int = None) -> tuple[bool, str]:
    """异步执行脚本，使用线程池避免阻塞"""
    return await asyncio.to_thread(run_script_sync, content, script_id, project_id, run_id)


async def execute_script_with_ai_fix(
    db: Session,
    run_id: int,
    script_id: int,
    project_id: int,
    script_content: str,
    script_name: str,
    target_url: str = "",
    auto_fix: bool = True,
    max_retries: int = 2,
    params: Optional[dict] = None,
    headless: bool = True,
    executor: str = "celery",
) -> dict:
    """
    执行自动化脚本（支持 AI 自动修复重试）

    Args:
        db: 数据库会话
        run_id: 执行记录ID
        script_id: 脚本ID
        project_id: 项目ID
        script_content: 脚本内容
        script_name: 脚本名称
        target_url: 目标URL
        auto_fix: 是否自动修复
        max_retries: 最大重试次数
        params: 脚本参数
        headless: 是否无头模式运行浏览器
        executor: 执行来源标记（celery / background）

    Returns:
        执行结果字典
    """
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
    if not run or not script:
        logger.error(f"任务执行失败: run={run_id} 或 script={script_id} 不存在")
        return {"status": "failed", "error": "执行记录或脚本不存在"}

    current_content = apply_headless_mode(apply_params(script_content, params), headless)
    start_time = time.time()
    start_datetime = run.started_at or china_now_naive()
    error_msg = ""
    status_result = "passed"
    retry_count = 0
    exec_log = [
        {
            "action": "script_run",
            "detail": f"执行脚本: {script_name}",
            "timestamp": start_time,
            "status": "running",
            "script_id": script_id,
            "executor": executor,
        }
    ]

    # 首次执行
    success, error_msg = await execute_script_async(current_content, script_id, project_id, run_id)
    duration = time.time() - start_time

    # 收集本次执行的步骤日志（脚本中 '# 步骤N: xxx' 注释转换而来）
    step_logs = get_last_step_logs()
    for sl in step_logs:
        exec_log.append(sl)

    if success:
        exec_log.append({
            "action": "result",
            "detail": f"执行成功，耗时: {duration:.2f}s",
            "timestamp": time.time(),
            "status": "passed",
            "duration": round(duration, 3),
        })
    else:
        exec_log.append({
            "action": "result",
            "detail": f"第1次执行失败，耗时: {duration:.2f}s, 错误: {error_msg}",
            "timestamp": time.time(),
            "status": "failed",
            "duration": round(duration, 3),
            "error": error_msg,
            "attempt": 1,
        })

        # 自动修复重试循环
        max_retries = max(0, max_retries)

        while not success and auto_fix and retry_count < max_retries:
            retry_count += 1
            logger.info(f"脚本 #{script_id} 执行失败，开始第 {retry_count} 次AI修复重试")
            exec_log.append({
                "action": "ai_fix",
                "detail": f"调用AI修复脚本（第{retry_count}次）",
                "timestamp": time.time(),
                "status": "running",
                "attempt": retry_count,
            })

            # 创建 AgentTask 记录（AI修复脚本）
            fix_task = AgentTask(
                project_id=project_id,
                agent_type="script_fixer",
                status="running",
                input_params={
                    "script_id": script_id,
                    "script_name": script_name,
                    "run_id": run_id,
                    "attempt": retry_count,
                    "error_message": error_msg[:500],
                    "executor": executor,
                },
                created_by=run.executed_by,
            )
            db.add(fix_task)
            db.flush()
            fix_task_id = fix_task.id
            db.commit()

            try:
                fixed_content = await ScriptGenerator.fix_script_with_ai(
                    script_content=current_content,
                    error_message=error_msg,
                    script_name=script_name,
                    target_url=target_url or "",
                    db_session=db,
                )

                if fixed_content == current_content:
                    exec_log.append({
                        "action": "ai_fix",
                        "detail": "AI修复未产生变化，停止重试",
                        "timestamp": time.time(),
                        "status": "skipped",
                        "attempt": retry_count,
                    })
                    fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                    if fix_task:
                        fix_task.status = "success"
                        fix_task.output_result = {"result": "no_change", "attempt": retry_count}
                        fix_task.completed_at = china_now_naive()
                        db.commit()
                    break

                current_content = fixed_content
                exec_log.append({
                    "action": "ai_fix",
                    "detail": f"AI修复完成，修复后脚本长度: {len(fixed_content)}",
                    "timestamp": time.time(),
                    "status": "success",
                    "attempt": retry_count,
                })

                # 使用修复后的脚本重新执行
                retry_start = time.time()
                success, error_msg = await execute_script_async(current_content, script_id, project_id, run_id)
                retry_duration = time.time() - retry_start

                # 收集本次重试执行的步骤日志
                retry_step_logs = get_last_step_logs()
                for sl in retry_step_logs:
                    exec_log.append(sl)

                if success:
                    duration = time.time() - start_time
                    exec_log.append({
                        "action": "result",
                        "detail": f"第{retry_count + 1}次执行成功（修复后），耗时: {retry_duration:.2f}s",
                        "timestamp": time.time(),
                        "status": "passed",
                        "duration": round(retry_duration, 3),
                        "attempt": retry_count + 1,
                        "fixed": True,
                    })
                    status_result = "passed"
                    error_msg = ""

                    # 更新 AgentTask（修复成功）
                    fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                    if fix_task:
                        fix_task.status = "success"
                        fix_task.output_result = {"result": "fixed", "attempt": retry_count, "new_version": (script.version or 1) + 1}
                        fix_task.completed_at = china_now_naive()

                    # 修复成功后，更新脚本库中的脚本内容
                    try:
                        script.script_content = current_content
                        script.version = (script.version or 1) + 1
                        script.status = "active"
                        script.description = (script.description or "") + \
                            f"\n[自动修复] 执行失败后AI自动修复成功，版本升级至 v{script.version}"
                        db.commit()
                        exec_log.append({
                            "action": "script_updated",
                            "detail": f"脚本已自动更新至 v{script.version}",
                            "timestamp": time.time(),
                            "status": "success",
                            "new_version": script.version,
                        })
                        logger.info(f"脚本 #{script_id} 已自动修复并更新至 v{script.version}")
                    except Exception as update_e:
                        logger.warning(f"更新脚本库失败: {update_e}")
                        db.rollback()
                else:
                    exec_log.append({
                        "action": "result",
                        "detail": f"第{retry_count + 1}次执行失败（修复后），耗时: {retry_duration:.2f}s, 错误: {error_msg}",
                        "timestamp": time.time(),
                        "status": "failed",
                        "duration": round(retry_duration, 3),
                        "error": error_msg,
                        "attempt": retry_count + 1,
                        "fixed": True,
                    })
                    fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                    if fix_task:
                        fix_task.status = "failed"
                        fix_task.error_message = f"修复后执行仍失败: {error_msg[:300]}"
                        fix_task.completed_at = china_now_naive()
                        db.commit()

            except Exception as fix_e:
                error_msg = f"AI修复异常: {str(fix_e)}"
                logger.error(f"AI修复脚本异常: {fix_e}", exc_info=True)
                exec_log.append({
                    "action": "ai_fix",
                    "detail": f"AI修复异常: {str(fix_e)}",
                    "timestamp": time.time(),
                    "status": "failed",
                    "attempt": retry_count,
                })
                try:
                    fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                    if fix_task:
                        fix_task.status = "failed"
                        fix_task.error_message = str(fix_e)[:500]
                        fix_task.completed_at = china_now_naive()
                        db.commit()
                except Exception:
                    pass
                break

        if not success:
            status_result = "failed"
            duration = time.time() - start_time

    # 更新执行记录
    run.status = status_result
    run.error_message = error_msg
    run.duration = round(duration, 2)
    run.started_at = start_datetime
    run.completed_at = china_now_naive()
    run.execution_log = json.dumps(exec_log, ensure_ascii=False)
    db.commit()

    # 更新脚本统计
    script.total_runs = (script.total_runs or 0) + 1
    script.last_run_status = status_result
    script.last_run_at = china_now_naive()
    if status_result == "passed":
        script.pass_count = (script.pass_count or 0) + 1
    else:
        script.fail_count = (script.fail_count or 0) + 1
    db.commit()

    logger.info(
        f"脚本 #{script_id} 执行完成: "
        f"status={status_result}, duration={duration:.2f}s, retry_count={retry_count}, executor={executor}"
    )

    return {
        "status": status_result,
        "run_id": run_id,
        "script_id": script_id,
        "duration": round(duration, 2),
        "error": error_msg,
        "auto_fixed": status_result == "passed" and retry_count > 0,
        "retry_count": retry_count,
    }

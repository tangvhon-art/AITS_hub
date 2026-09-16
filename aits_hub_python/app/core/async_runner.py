"""
统一异步桥接工具：让同步上下文（Celery 任务 / Agent / 工具）安全地运行 async 逻辑。

## 为什么需要
macOS 上 Celery worker 使用 eventlet 协程池（-P eventlet），monkey-patch 后
threading.Thread / ThreadPoolExecutor / asyncio.to_thread 全部变成 greenlet，
所有任务挤在同一 OS 线程。当该 OS 线程已有一个 running event loop 时，再调用
``asyncio.run()`` / ``loop.run_until_complete()`` 会抛：
    Cannot run the event loop while another loop is running
（Python 3.12+ 由 ``BaseEventLoop._check_running`` 检测 ``_get_running_loop()`` 触发）

## 统一规范（新增代码必须遵守）
所有需要「在同步代码里把 async 函数跑到完」的入口，一律使用 :func:`run_async`，
**禁止**直接写 ``asyncio.run()`` / ``new_event_loop() + run_until_complete()``。

:func:`run_async` 会自动：
- 当前线程无 running loop → 直接在当前线程 ``asyncio.run``（最快路径）
- 当前线程已有 running loop（并发 greenlet 撞车）→ 调度到真实 OS 线程
  （eventlet 原始 Thread + 全新事件循环）执行，彻底隔离，永不报错。

## 兜底保护
:func:`install_worker_asyncio_guard` 会在 Celery worker 进程内 patch ``asyncio.run``，
即使未来某处直接调用 ``asyncio.run()`` 也会自动走安全路径，保证「后面的任务都不会
再出现这个错误」。该保护已在 ``app/celery_app.py`` 通过 worker 信号自动安装。
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def _get_real_thread_cls():
    """获取未被 eventlet monkey-patch 的原始 ``threading.Thread`` 类。

    eventlet 会把 threading.Thread 替换成 greenlet，导致所有「线程」挤在同一 OS
    线程上执行；这里取回真实 OS 线程类，用于隔离事件循环。
    """
    try:
        import eventlet.patcher
        return eventlet.patcher.original("threading").Thread
    except Exception:  # noqa: BLE001
        import threading
        return threading.Thread


def _check_coro_factory(fn):
    if asyncio.iscoroutine(fn):
        raise TypeError(
            "run_async() 需要传入协程工厂（async 函数 + 参数），而不是协程对象。"
            "正确：run_async(async_func, arg1, kw=...)；错误：run_async(async_func(...))"
        )


def run_in_real_thread(fn, *args, **kwargs):
    """在真实 OS 线程中运行任意同步函数。

    用于把「必须在无 running loop 的干净线程里执行」的逻辑隔离出去，
    规避 eventlet 绿色线程共享 OS 线程导致的 asyncio 冲突。
    """
    result = {}

    def _target():
        try:
            result["value"] = fn(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001
            result["error"] = e

    thread = _get_real_thread_cls()(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def run_coro_in_real_thread(coro_factory, *args, **kwargs):
    """在真实 OS 线程 + 全新事件循环中执行协程工厂，返回协程结果。

    :param coro_factory: async 函数（可调用对象），连同 *args/**kwargs 一起
        在真实线程里调用以创建协程。
    """
    _check_coro_factory(coro_factory)

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro_factory(*args, **kwargs))
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            loop.close()

    return run_in_real_thread(_runner)


def run_async(coro_factory, *args, **kwargs):
    """【统一入口】从同步上下文安全地把 async 函数跑到完。

    自动判断当前线程是否已有 running event loop：
    - 没有 → 直接在当前线程 ``asyncio.run``（最快，无线程切换）
    - 有（eventlet 并发 greenlet 场景）→ 调度到真实 OS 线程执行，彻底避开
      "Cannot run the event loop while another loop is running"。

    :param coro_factory: async 函数（可调用对象），连同 *args/**kwargs 传入。
        注意传入的是**函数 + 参数**，而不是调用后的协程对象。
    """
    _check_coro_factory(coro_factory)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 当前线程没有 running loop：直接在当前线程执行
        return asyncio.run(coro_factory(*args, **kwargs))

    # 当前线程已有 running loop（eventlet 并发场景）：真实 OS 线程隔离执行
    return run_coro_in_real_thread(coro_factory, *args, **kwargs)


# ---------------------------------------------------------------------------
# Celery worker 级兜底保护：patch asyncio.run，保证未来遗漏的直接调用也不崩
# ---------------------------------------------------------------------------

_ORIGINAL_ASYNCIO_RUN = asyncio.run


def _safe_asyncio_run(main, *args, **kwargs):
    """``asyncio.run`` 的安全包装：当前线程已有 running loop 时调度到真实 OS 线程。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _ORIGINAL_ASYNCIO_RUN(main, *args, **kwargs)
    # 当前线程已有 running loop → 在真实 OS 线程里跑完整的 asyncio.run
    return run_in_real_thread(lambda: _ORIGINAL_ASYNCIO_RUN(main, *args, **kwargs))


def install_worker_asyncio_guard():
    """在 Celery worker 进程内安装 ``asyncio.run`` 安全兜底（幂等）。

    仅应在 worker 进程内调用（见 app/celery_app.py 的 worker_init /
    worker_process_init 信号注册），避免影响 FastAPI 后端进程。
    安装后，任何直接 ``asyncio.run()`` 的代码在事件循环冲突场景下也会自动
    转到真实 OS 线程执行，从而保证「后面的任务都不会再出现这个问题」。
    """
    if asyncio.run is _safe_asyncio_run:
        return
    asyncio.run = _safe_asyncio_run
    logger.info("[async_runner] 已在 worker 内安装 asyncio.run 兜底保护")

import functools
import inspect
import time
from typing import Any

from prometheus_client import Counter, Histogram
from starlette.background import BackgroundTasks

background_task_scheduled_total = Counter(
    "background_task_scheduled_total",
    "Background tasks scheduled (BackgroundTasks.add_task calls), by mode.",
    labelnames=["mode"],
)
background_task_total = Counter(
    "background_task_total",
    "Background tasks completed, labeled by execution mode and outcome.",
    labelnames=["mode", "outcome"],
)
background_task_duration_seconds = Histogram(
    "background_task_duration_seconds",
    "Background task wall-clock duration in seconds.",
    labelnames=["mode"],
    # Background work can run far longer than HTTP requests, so extend past the
    # default 10s ceiling.
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)


def _is_async_callable(obj: Any) -> bool:
    # Mirror of starlette._utils.is_async_callable so the mode label always
    # matches how starlette will actually dispatch (async vs run_in_threadpool).
    # Notably handles functools.partial(async_func, ...), which a plain
    # inspect.iscoroutinefunction misclassifies as sync.
    while isinstance(obj, functools.partial):
        obj = obj.func
    return inspect.iscoroutinefunction(obj) or (
        callable(obj) and inspect.iscoroutinefunction(obj.__call__)
    )


def _record(mode: str, start: float, *, ok: bool) -> None:
    background_task_total.labels(mode=mode, outcome="ok" if ok else "error").inc()
    background_task_duration_seconds.labels(mode=mode).observe(
        time.perf_counter() - start
    )


def _wrap_async(func: Any) -> Any:
    @functools.wraps(func)
    async def async_wrapper(*a: Any, **kw: Any) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*a, **kw)
        except BaseException:
            _record("async", start, ok=False)
            raise
        _record("async", start, ok=True)
        return result

    return async_wrapper


def _wrap_sync(func: Any) -> Any:
    @functools.wraps(func)
    def sync_wrapper(*a: Any, **kw: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*a, **kw)
        except BaseException:
            _record("threadpool", start, ok=False)
            raise
        _record("threadpool", start, ok=True)
        return result

    return sync_wrapper


def install_patch() -> None:
    """Monkey-patch starlette.background.BackgroundTasks.add_task once.

    Idempotent. The patch is process-global — every FastAPI app in this
    process gets background-task instrumentation. Pass
    ``background_task_metrics=False`` to ``install(app)`` to skip this step.
    """
    if getattr(BackgroundTasks.add_task, "_observability_wrapped", False):
        return

    original_add_task = BackgroundTasks.add_task

    def instrumented_add_task(
        self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any
    ) -> None:
        if _is_async_callable(func):
            background_task_scheduled_total.labels(mode="async").inc()
            wrapper = _wrap_async(func)
        else:
            background_task_scheduled_total.labels(mode="threadpool").inc()
            wrapper = _wrap_sync(func)
        return original_add_task(self, wrapper, *args, **kwargs)

    instrumented_add_task._observability_wrapped = True  # type: ignore[attr-defined]
    BackgroundTasks.add_task = instrumented_add_task  # type: ignore[method-assign]

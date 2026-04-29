import anyio.to_thread
from prometheus_client import Gauge

threadpool_tokens = Gauge(
    "threadpool_tokens",
    "Threadpool token counts in anyio's default thread limiter, by state.",
    labelnames=["state"],
)
threadpool_tasks_waiting = Gauge(
    "threadpool_tasks_waiting",
    "Tasks queued waiting to acquire a threadpool token.",
)


def refresh() -> None:
    # Must be called from the event loop: current_default_thread_limiter() reads
    # a loop-scoped ContextVar.
    stats = anyio.to_thread.current_default_thread_limiter().statistics()
    threadpool_tokens.labels(state="total").set(stats.total_tokens)
    threadpool_tokens.labels(state="borrowed").set(stats.borrowed_tokens)
    threadpool_tokens.labels(state="available").set(
        stats.total_tokens - stats.borrowed_tokens
    )
    threadpool_tasks_waiting.set(stats.tasks_waiting)

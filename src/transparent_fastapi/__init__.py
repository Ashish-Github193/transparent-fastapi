"""transparent-fastapi: drop-in Prometheus metrics for FastAPI."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from importlib.metadata import version as _version

from fastapi import FastAPI

from transparent_fastapi import background_tasks, http
from transparent_fastapi.endpoint import metrics_endpoint
from transparent_fastapi.event_loop import measure_event_loop_lag

__version__ = _version("transparent-fastapi")

__all__ = ["__version__", "install"]


def install(
    app: FastAPI,
    *,
    excluded_paths: Iterable[str] | None = None,
    background_task_metrics: bool = True,
) -> None:
    """Install transparent-fastapi observability into a FastAPI app.

    Wires up:
      - Two HTTP middlewares: in-flight gauge and request counter/histogram.
      - A ``/metrics`` endpoint exposing Prometheus exposition format.
      - A background event-loop-lag sampler attached to the app's lifespan.
      - Optionally, a process-global monkey-patch on
        ``starlette.background.BackgroundTasks`` that instruments every
        ``add_task(...)`` call with ok/error counts and a duration histogram.

    Must be called before the app starts serving traffic (typically right
    after ``app = FastAPI(...)``).

    Args:
        app: The FastAPI app to instrument.
        excluded_paths: Exact request paths to skip in HTTP metrics. Useful
            for noisy health/readiness probes.
        background_task_metrics: If False, skip the BackgroundTasks patch.
            The patch is process-global; turn off if you have multiple
            FastAPI apps in the same process and only want some instrumented.
    """
    excluded = frozenset(excluded_paths or ())

    app.middleware("http")(http.make_in_flight_middleware(excluded))
    app.middleware("http")(http.make_request_metrics_middleware(excluded))
    app.get("/metrics", include_in_schema=False)(metrics_endpoint)

    _wrap_lifespan(app)

    if background_task_metrics:
        background_tasks.install_patch()


def _wrap_lifespan(app: FastAPI) -> None:
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan_with_observability(app: FastAPI) -> AsyncIterator[None]:
        async with original_lifespan(app):
            lag_task = asyncio.create_task(measure_event_loop_lag())
            try:
                yield
            finally:
                lag_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await lag_task

    app.router.lifespan_context = lifespan_with_observability

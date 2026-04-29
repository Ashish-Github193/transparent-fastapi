# CLAUDE.md

## Scope

The library proper. Every file in this directory ships in the PyPI wheel; nothing outside this directory does. Public API is whatever `__init__.py.__all__` exports — currently just `install` and `__version__`.

## Module map

| File | Role |
|---|---|
| `__init__.py` | Public API + `_wrap_lifespan()` (auto-attaches the event-loop-lag sampler to the app's lifespan). |
| `http.py` | Request counter/histogram/in-flight gauge + the two middleware factories. |
| `event_loop.py` | `event_loop_lag_seconds` gauge + the sampler task. |
| `threadpool.py` | Labeled `threadpool_tokens` gauge + `refresh()`, called at scrape time. |
| `endpoint.py` | `/metrics` handler — calls `threadpool.refresh()` then `generate_latest()`. |
| `background_tasks.py` | Counter/Histogram + the monkey-patch on `BackgroundTasks.add_task`. |

## Patterns to follow

- **Metrics declared at module scope.** They register with prometheus_client's default registry on import. Don't construct gauges/counters inside `install()` — re-registration is an error.
- **Middleware that needs runtime config is a factory function.** See `make_in_flight_middleware`/`make_request_metrics_middleware`: the factory closes over config and returns the actual middleware. Avoids module-level mutable state.
- **Prefer scrape-time refresh over polling** for state-at-snapshot metrics. The threadpool gauges are refreshed inside `endpoint.metrics_endpoint()` rather than by a background task — the values are always live and we don't pay for polling between scrapes.

## Pitfalls

- **`scope["route"]` is populated by Router DURING dispatch**, so it's only readable after `call_next` returns. The middleware reads it post-call_next; reading it before would always yield `<unmatched>`.
- **`asyncio.iscoroutinefunction` is deprecated in Python 3.14.** Use `inspect.iscoroutinefunction`. For background-task detection, prefer the local `_is_async_callable` helper — it mirrors starlette's own detector and correctly classifies `functools.partial(async_fn)` as async.
- **Don't import from `starlette._utils`.** Private API. We mirror its logic locally so we don't break when starlette refactors internals.
- **The monkey-patch sentinel** lives at `BackgroundTasks.add_task._observability_wrapped`. It's how `install_patch()` is idempotent. If you re-implement the patch, keep the sentinel.

## When adding a new metric

1. Declare the metric (Counter/Gauge/Histogram) at module scope in the appropriate file.
2. Update the README's "What it exports" table.
3. Add a smoke test that hits a route, scrapes `/metrics`, and asserts the family appears.
4. If the metric needs scrape-time refresh, call its `refresh()` from `endpoint.metrics_endpoint`.

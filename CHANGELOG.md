# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-30

Initial release.

### Added
- `install(app, *, excluded_paths=None, background_task_metrics=True)` — one-call setup that wires up middlewares, the `/metrics` endpoint, and the event-loop-lag sampler on the app's lifespan.
- HTTP metrics: `http_requests_total`, `http_request_duration_seconds`, `http_requests_in_flight`, with route labels taken from FastAPI path templates and a `<unmatched>` sentinel for unknown paths.
- Runtime metrics: `event_loop_lag_seconds`, `threadpool_tokens` (state ∈ {total, borrowed, available}), `threadpool_tasks_waiting`.
- BackgroundTasks instrumentation via an idempotent monkey-patch on `starlette.background.BackgroundTasks.add_task`: `background_task_scheduled_total`, `background_task_total` (mode × outcome), `background_task_duration_seconds`.
- `py.typed` marker — the package ships type information.

[Unreleased]: https://github.com/Ashish-Github193/transparent-fastapi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ashish-Github193/transparent-fastapi/releases/tag/v0.1.0

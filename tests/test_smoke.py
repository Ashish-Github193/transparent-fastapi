"""Smoke tests for transparent-fastapi.install()."""

import re

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from transparent_fastapi import install


def _build_app(**install_kwargs):
    app = FastAPI()
    install(app, **install_kwargs)

    @app.get("/hello")
    async def hello():
        return {"ok": True}

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        return {"id": item_id}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def test_metrics_endpoint_exposes_expected_families() -> None:
    client = TestClient(_build_app())
    assert client.get("/hello").status_code == 200

    body = client.get("/metrics").text
    for family in (
        "http_requests_total",
        "http_request_duration_seconds",
        "http_requests_in_flight",
        "event_loop_lag_seconds",
        "threadpool_tokens",
        "threadpool_tasks_waiting",
    ):
        assert family in body, f"expected {family} in /metrics output"


def test_route_label_uses_template_not_raw_path() -> None:
    client = TestClient(_build_app())
    for item_id in ("1", "2", "3"):
        client.get(f"/items/{item_id}")

    body = client.get("/metrics").text
    assert 'route="/items/{item_id}"' in body
    assert 'route="/items/1"' not in body
    assert 'route="/items/2"' not in body


def test_unmatched_path_collapses_to_sentinel() -> None:
    client = TestClient(_build_app())
    client.get("/this/does/not/exist")
    client.get("/another/scanner/probe")

    body = client.get("/metrics").text
    assert 'route="<unmatched>"' in body
    assert 'route="/this/does/not/exist"' not in body


def test_excluded_paths_skip_metrics() -> None:
    client = TestClient(_build_app(excluded_paths=["/health"]))
    client.get("/health")
    client.get("/health")
    client.get("/hello")

    body = client.get("/metrics").text
    assert 'route="/hello"' in body
    assert 'route="/health"' not in body


def test_background_task_metrics_via_route() -> None:
    app = FastAPI()
    install(app)

    @app.post("/schedule")
    async def schedule(bt: BackgroundTasks):
        async def _async_task():
            pass

        def _sync_task():
            pass

        bt.add_task(_async_task)
        bt.add_task(_sync_task)
        return {"queued": True}

    client = TestClient(app)
    assert client.post("/schedule").status_code == 200

    body = client.get("/metrics").text
    assert 'background_task_total{mode="async",outcome="ok"}' in body
    assert 'background_task_total{mode="threadpool",outcome="ok"}' in body
    assert 'background_task_scheduled_total{mode="async"}' in body
    assert 'background_task_scheduled_total{mode="threadpool"}' in body


def test_install_is_idempotent_for_background_patch() -> None:
    app1 = FastAPI()
    app2 = FastAPI()
    install(app1)
    install(app2)  # second install must not double-wrap the patch

    from starlette.background import BackgroundTasks as _BT

    assert getattr(_BT.add_task, "_observability_wrapped", False) is True


def test_cardinality_stays_bounded_under_adversarial_traffic() -> None:
    # The library's whole pitch: hostile inputs (random path-param values,
    # scanner probes, exotic verbs) must not grow the route or method label
    # space beyond declared templates + sentinels.
    client = TestClient(_build_app())

    for i in range(200):
        client.get(f"/items/{i}")

    for i in range(200):
        client.get(f"/scanner/probe/{i}")

    for verb in ("PROPFIND", "PURGE", "MKCOL", "COPY", "MOVE"):
        client.request(verb, "/hello")

    body = client.get("/metrics").text
    routes = set(
        re.findall(r'http_requests_total\{[^}]*route="([^"]*)"', body)
    )
    methods = set(
        re.findall(r'http_requests_total\{[^}]*method="([^"]*)"', body)
    )

    # Hard upper bound: 405 distinct adversarial inputs should not balloon the
    # route label space. Other tests in this file legitimately register a
    # handful of routes, so we allow slack but cap well below 405.
    assert len(routes) < 15, f"route cardinality blew up: {len(routes)} -> {routes}"

    raw_leaks = {
        r for r in routes
        if (r.startswith("/items/") and r != "/items/{item_id}")
        or r.startswith("/scanner/")
    }
    assert not raw_leaks, f"raw paths leaked into route label: {raw_leaks}"

    allowed_methods = {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
        "OTHER",
    }
    extra_methods = methods - allowed_methods
    assert not extra_methods, f"unexpected method labels: {extra_methods}"

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram

http_requests_in_flight = Gauge(
    "http_requests_in_flight",
    "Number of HTTP requests currently being processed.",
)
http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests handled, by method, route, and status.",
    labelnames=["method", "route", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request wall-clock duration in seconds.",
    labelnames=["method", "route"],
)

# Allowlist standard verbs; anything else (rare and usually adversarial) becomes
# OTHER so a single oddly-shaped request can't grow cardinality.
_KNOWN_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)

Middleware = Callable[
    [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
]


def _method_label(method: str) -> str:
    return method if method in _KNOWN_METHODS else "OTHER"


def _route_label(request: Request) -> str:
    # request.scope["route"] is populated by FastAPI's APIRoute during dispatch
    # — only readable AFTER call_next. Falls back to a fixed sentinel rather
    # than the raw URL — never label with raw paths, otherwise a single port
    # scan can balloon series count.
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "<unmatched>"


def make_in_flight_middleware(excluded: frozenset[str]) -> Middleware:
    async def track_in_flight(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.scope.get("path") in excluded:
            return await call_next(request)
        http_requests_in_flight.inc()
        try:
            return await call_next(request)
        finally:
            http_requests_in_flight.dec()

    return track_in_flight


def make_request_metrics_middleware(excluded: frozenset[str]) -> Middleware:
    async def track_request_metrics(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.scope.get("path") in excluded:
            return await call_next(request)
        method = _method_label(request.method)
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            # Read route after call_next so Router has had a chance to populate
            # it. finally runs on both success and exception paths; on exception
            # status stays "500" (set above) and we still record the failure.
            route = _route_label(request)
            http_requests_total.labels(
                method=method, route=route, status=status
            ).inc()
            http_request_duration_seconds.labels(
                method=method, route=route
            ).observe(time.perf_counter() - start)

    return track_request_metrics

"""Demo FastAPI app baked into the docker image for the local stack.

It exists so deploy/local has something to scrape. The /sleep-async and
/sleep-sync routes are the headline demo: same handler shape, one yields to
the event loop and one blocks it — visible in event_loop_lag_seconds and
http_request_duration_seconds under load.
"""

import asyncio
import time
from typing import Annotated
import random
from fastapi import BackgroundTasks, FastAPI, Query

from transparent_fastapi import install

app = FastAPI(title="transparent-fastapi demo")

install(app, excluded_paths=["/health"])


@app.get("/hello")
async def hello() -> dict:
    return {"hello": "world"}


@app.get("/items/{item_id}")
async def get_item(item_id: str) -> dict:
    # Path-param route: every request collapses to route="/items/{item_id}"
    # in metrics regardless of the {item_id} value, demonstrating the
    # cardinality-discipline guarantee. Hit by locust with varying IDs.
    return {"id": item_id}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/sleep-async")
async def sleep_async(
    seconds: Annotated[float, Query(ge=0, le=10)] = 0.5,
) -> dict:
    await asyncio.sleep(seconds)
    return {"slept": seconds, "mode": "async"}


@app.get("/sleep-sync")
async def sleep_sync(
    seconds: Annotated[float, Query(ge=0, le=10)] = 0.5,
) -> dict:
    # time.sleep inside an async handler blocks the event loop thread for the
    # full duration — every other request stalls behind it. Useful for
    # demonstrating event_loop_lag_seconds spikes under load.
    time.sleep(seconds)
    return {"slept": seconds, "mode": "sync-blocking"}


@app.get("/boom")
async def boom() -> dict:
    # Surfaces as an unhandled 500. Drives the http_request_total{status="5xx"}
    # counter and the error path of the in-flight gauge.
    raise RuntimeError("boom")


@app.get("/threadpool")
def threadpool(
    seconds: Annotated[float, Query(ge=0, le=10)] = 0.5,
) -> dict:
    # Plain `def` (not `async def`): Starlette dispatches it to anyio's default
    # threadpool, borrowing a token for the duration. Hammering this endpoint
    # is what makes threadpool_tokens{state="borrowed"} rise and
    # threadpool_tasks_waiting go non-zero.
    time.sleep(seconds)
    return {"slept": seconds, "mode": "threadpool"}


@app.post("/notify")
async def notify(
    background_tasks: BackgroundTasks,
    seconds: Annotated[float, Query(ge=0, le=10)] = 0.1,
) -> dict:
    # Schedules one sync and one async background task so both modes show up
    # under background_task_total{mode="threadpool"|"async"}.
    def _bg_sync(seconds: float) -> None:
        if random.uniform(0, 1) > .1:
            time.sleep(seconds)
            return
        raise Exception("_bg_sync task failed")

    background_tasks.add_task(_bg_sync, seconds)

    async def _bg_async(seconds: float) -> None:
        if random.uniform(0, 1) > .1:
            await asyncio.sleep(seconds)
            return
        raise Exception("_bg_async task failed")

    background_tasks.add_task(_bg_async, seconds)

    return {"scheduled": 2, "seconds": seconds}

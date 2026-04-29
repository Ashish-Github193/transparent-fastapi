"""Demo FastAPI app baked into the docker image for the local stack.

It exists so deploy/local has something to scrape. The /sleep-async and
/sleep-sync routes are the headline demo: same handler shape, one yields to
the event loop and one blocks it — visible in event_loop_lag_seconds and
http_request_duration_seconds under load.
"""

import asyncio
import time
from typing import Annotated

from fastapi import FastAPI, Query

from transparent_fastapi import install

app = FastAPI(title="transparent-fastapi demo")

install(app, excluded_paths=["/health"])


@app.get("/hello")
async def hello() -> dict:
    return {"hello": "world"}


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

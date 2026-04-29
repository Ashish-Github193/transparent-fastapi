import asyncio

from prometheus_client import Gauge

LAG_SAMPLE_INTERVAL = 1.0

event_loop_lag_seconds = Gauge(
    "event_loop_lag_seconds",
    "Delta between expected and actual wake-up of a 1s sleep on the event loop.",
)


async def measure_event_loop_lag() -> None:
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(LAG_SAMPLE_INTERVAL)
        event_loop_lag_seconds.set(loop.time() - t0 - LAG_SAMPLE_INTERVAL)

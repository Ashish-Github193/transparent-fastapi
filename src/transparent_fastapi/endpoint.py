from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from transparent_fastapi import threadpool


async def metrics_endpoint() -> Response:
    threadpool.refresh()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

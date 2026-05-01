# Multi-stage build for the test_server demo image. Two targets are exposed,
# selected by the consuming compose file via `build.target:`:
#
#   - source-build  install transparent-fastapi from the workspace source tree
#                   (deploy/source/docker-compose.yml).
#   - live-build    install the published wheel from PyPI for release
#                   verification (deploy/live/docker-compose.yml).
#
# Stages are independent — neither references the other. Shared scaffolding
# (uvicorn install, EXPOSE, CMD) lives in `base`.

FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir "uvicorn[standard]>=0.32"
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base AS source-build
# test_server's own pyproject is a thin workspace-membership declaration; we
# install runtime deps directly to keep the image lean.
COPY pyproject.toml README.md LICENSE ./
COPY src/transparent_fastapi/ ./src/transparent_fastapi/
RUN pip install --no-cache-dir .
COPY src/test_server/app.py ./app.py


FROM base AS live-build
# Pin to a released version so the image is auditable in git. Override at
# build time via TFA_VERSION (see deploy/live/docker-compose.yml).
ARG TFA_VERSION=0.1.2
RUN pip install --no-cache-dir "transparent-fastapi==${TFA_VERSION}"
COPY src/test_server/app.py ./app.py

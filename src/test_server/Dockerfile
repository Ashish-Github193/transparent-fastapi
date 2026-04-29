FROM python:3.12-slim

WORKDIR /app

# Install the library from the workspace source tree, then uvicorn separately
# (test_server's own pyproject is a thin workspace-membership declaration; the
# Dockerfile installs the actual runtime deps directly to keep the image lean).
COPY pyproject.toml README.md LICENSE ./
COPY src/transparent_fastapi/ ./src/transparent_fastapi/
RUN pip install --no-cache-dir . \
 && pip install --no-cache-dir "uvicorn[standard]>=0.32"

COPY src/test_server/app.py ./app.py

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

# Multi-stage Dockerfile for Runport
# 1. Build React/TypeScript frontend
FROM node:20-slim AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. Build Python wheel with bundled frontend
FROM python:3.11-slim AS wheel-builder
WORKDIR /app
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src/ ./src/
COPY --from=web-builder /app/web/dist/ ./src/runport/_web/
RUN pip wheel --no-deps -w /dist .

# 3. Lean non-root runtime
FROM python:3.11-slim AS runtime
LABEL org.opencontainers.image.source="https://github.com/Sudharsanselvaraj/runport"
LABEL org.opencontainers.image.description="Universal open-source LLM, prompt, and workflow benchmarking platform"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Create non-root user
RUN groupadd -g 10001 runport && \
    useradd -u 10001 -g runport -m -s /bin/bash runport

WORKDIR /workspace

# Install wheel and dependencies
COPY --from=wheel-builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    RUNPORT_HOST=0.0.0.0 \
    RUNPORT_PORT=8000

# Create local data and report directories
RUN mkdir -p /workspace/data /workspace/reports && \
    chown -R runport:runport /workspace

USER runport

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

# When bound to 0.0.0.0 inside a container, RUNPORT_API_TOKEN is recommended for remote access
# Usage:
#   docker run -p 127.0.0.1:8000:8000 -v $(pwd)/data:/workspace/data runport:latest
CMD ["runport", "web", "--host", "0.0.0.0", "--port", "8000"]

# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS web-builder
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv-bin

FROM python:3.13.17-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH \
    TAVILY_MUX_CONFIG_FILE=/data/config.yaml \
    TAVILY_MUX_DATA_DIR=/data \
    TAVILY_MUX_WEB_ROOT=/app/web \
    TAVILY_MUX_HOST=0.0.0.0 \
    TAVILY_MUX_PORT=8080

RUN groupadd --system --gid 10001 tavily-mux \
    && useradd --system --uid 10001 --gid tavily-mux --home-dir /app tavily-mux \
    && mkdir -p /app /data \
    && chown -R tavily-mux:tavily-mux /app /data

COPY --from=uv-bin /uv /uvx /usr/local/bin/
WORKDIR /app
COPY --chown=tavily-mux:tavily-mux pyproject.toml uv.lock README.md ./
COPY --chown=tavily-mux:tavily-mux src/ ./src/
RUN uv sync --frozen --no-dev --no-editable
COPY --from=web-builder --chown=tavily-mux:tavily-mux /build/web/dist/ /app/web/

USER tavily-mux
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2)"]
ENTRYPOINT ["tavily-mux"]

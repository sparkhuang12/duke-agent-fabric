FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
COPY backend ./backend
RUN python -m pip wheel --wheel-dir /wheels '.[production]'

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DUKE_AGENT_CONFIG_PATH=/app/config/agents.json \
    DUKE_SKILLS_MANIFEST_PATH=/app/skills/manifest.json \
    DUKE_STATIC_DIR=/app/prototype

RUN groupadd --system duke && useradd --system --gid duke --home-dir /app duke
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=duke:duke backend ./backend
COPY --chown=duke:duke config ./config
COPY --chown=duke:duke policies ./policies
COPY --chown=duke:duke prototype ./prototype
COPY --chown=duke:duke skills ./skills
RUN mkdir -p /app/data && chown duke:duke /app/data

USER duke
EXPOSE 9090
HEALTHCHECK --interval=20s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/api/v1/health/ready', timeout=2)"

CMD ["uvicorn", "duke_harness.api.app:app", "--host", "0.0.0.0", "--port", "9090", "--proxy-headers", "--no-server-header"]

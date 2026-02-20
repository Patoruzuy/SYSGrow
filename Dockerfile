# ─── SYSGrow Backend ───────────────────────────────────────────────
# Multi-stage build for the SYSGrow Smart Agriculture backend.
#
# Build:
#   docker build -t sysgrow-backend .
#
# With Zigbee support (Linux / Raspberry Pi):
#   docker build --build-arg INSTALL_ZIGBEE=true -t sysgrow-backend .
#
# Run:
#   docker run -p 8000:8000 -v ./database:/app/database sysgrow-backend
# ───────────────────────────────────────────────────────────────────

# ── Stage 1: builder ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements-essential.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements-essential.txt

# Optional: Zigbee support (zigpy + adapters)
ARG INSTALL_ZIGBEE=false
COPY setup.py pyproject.toml ./
COPY app/ app/
RUN if [ "$INSTALL_ZIGBEE" = "true" ]; then \
        pip install --no-cache-dir --prefix=/install ".[zigbee]"; \
    fi


# ── Stage 2: runtime ─────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# curl is needed for Docker HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r sysgrow && useradd -r -g sysgrow -d /app sysgrow

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY smart_agriculture_app.py setup.py pyproject.toml ./
COPY app/                 app/
COPY templates/           templates/
COPY static/              static/
COPY infrastructure/      infrastructure/
COPY migrations/          migrations/
COPY data/                data/
COPY scripts/             scripts/

# Create writable directories
RUN mkdir -p database logs var \
    && chown -R sysgrow:sysgrow /app

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SYSGROW_ENV=production \
    SYSGROW_HOST=0.0.0.0 \
    SYSGROW_PORT=8000 \
    SYSGROW_DATABASE_PATH=/app/database/sysgrow.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/v1/health/live || exit 1

USER sysgrow

CMD ["gunicorn", \
     "--worker-class", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "smart_agriculture_app:app"]

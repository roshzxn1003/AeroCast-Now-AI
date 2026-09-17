# ==============================================================================
# AeroCast-Now AI: Hardened Multi-Stage Backend Dockerfile (Phase 12)
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Minimal Non-Root Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime utilities (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create unprivileged non-root user and group
RUN groupadd -g 10001 aerocast && \
    useradd -u 10001 -g aerocast -s /bin/bash -m aerocast

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AEROCAST_ENV=production

# Prepare persistent mount points and permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R aerocast:aerocast /app

# Copy application source code
COPY --chown=aerocast:aerocast . /app

# Switch to unprivileged user
USER aerocast

EXPOSE 8000

# Container Readiness Healthcheck Probe
HEALTHCHECK --interval=20s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/ready || exit 1

# Production Entrypoint
CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]

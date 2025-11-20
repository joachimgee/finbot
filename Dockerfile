# FinBot Dockerfile - Multi-stage Production Build
# Optimized for security, size, and performance

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim as builder

LABEL stage="builder"

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --user --no-cache-dir --no-warn-script-location \
    -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

LABEL maintainer="FinBot Team <dev@finbot.ai>"
LABEL version="1.0.0"
LABEL description="FinBot - Algorithmic Trading Engine"
LABEL org.opencontainers.image.source="https://github.com/joachimgee/finbot"
LABEL org.opencontainers.image.documentation="https://github.com/joachimgee/finbot/blob/main/README.md"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash finbot && \
    mkdir -p /app /app/logs /app/data && \
    chown -R finbot:finbot /app

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder --chown=finbot:finbot /root/.local /home/finbot/.local

# Add user site-packages to PATH
ENV PATH=/home/finbot/.local/bin:$PATH \
    PYTHONPATH=/app:$PYTHONPATH

# Copy application code
COPY --chown=finbot:finbot . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    DEBUG=False \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    TZ=UTC

# PYTHONHASHSEED=0
# ----------------------------------------------
# Utilisation d'un seed de hachage FIXE en production pour :
# 1. Garantir le déterminisme (hash stable des clés dict / sets)
# 2. Éviter des écarts difficiles à reproduire dans des algorithmes sensibles
# 3. Faciliter le debug et la comparaison de traces
# Pour activer la randomisation à l'exécution (ex: tests de robustesse):
#   docker run -e PYTHONHASHSEED=random finbot:latest

# Create necessary directories
RUN mkdir -p logs data && \
    touch logs/.gitkeep data/.gitkeep && \
    chown -R finbot:finbot logs data

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER finbot

# Expose application port
EXPOSE 8000

# Use tini for proper signal handling and zombie reaping
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command: run Gunicorn with Uvicorn workers
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--graceful-timeout", "30", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "financial_analyzer.api.main:app"]

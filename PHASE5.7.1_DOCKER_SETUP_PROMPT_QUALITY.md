# 🎯 PHASE 5.7.1 - DOCKER SETUP PROMPT

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10) - DONE
✅ Phase 5.6      : Integration & Validation (9.1/10) - DONE
🚀 Phase 5.7.1    : Docker Setup - NOW! (Quality > Speed)
```

---

## CONTEXT

**Phase 5.7.1** implémente **Docker containerization** pour FinBot :
- Dockerfile production-ready (python:3.11-slim)
- docker-compose orchestration (app + redis + postgres + nginx)
- Multi-service architecture
- Development vs Production configs
- Security best practices

**Objectif** : Infrastructure robuste, scalable, prête pour production

**Approche** : QUALITÉ MAXIMALE (correctifs inclus, documentation complète)

---

## 📚 INSPIRATIONS AUDITS & BEST PRACTICES

**Référez-vous à** :
1. AUDIT_BACKTESTING_PY.md - Performance patterns
2. AUDIT_FINANCE_PARTIE_1_OVERVIEW.md - System architecture

---

## 📄 PROMPT FOR COPILOT (QUALITY VERSION)

**COPY-PASTE ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.7.1 : DOCKER SETUP - PRODUCTION QUALITY

Génère 7 fichiers Docker + config pour FinBot:

================================================================================
1. Dockerfile (80 LOC) - Multi-stage, production-ready
================================================================================

FROM python:3.11-slim as builder

# Stage 1: Build dependencies
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

LABEL maintainer="FinBot Team <dev@finbot.ai>"
LABEL version="1.0.0"
LABEL description="FinBot - Algorithmic Trading Engine"

# Install runtime dependencies only (slim image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 finbot

WORKDIR /app

# Copy from builder
COPY --from=builder /root/.local /home/finbot/.local
ENV PATH=/home/finbot/.local/bin:$PATH

# Copy application code
COPY --chown=finbot:finbot . .

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBUG=False \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER finbot

# Expose ports
EXPOSE 8000

# Use tini to handle signals properly
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "financial_analyzer.api.main:app"]

================================================================================
2. docker-compose.yml (120 LOC) - Multi-service orchestration
================================================================================

version: '3.9'

services:
  # Main FinBot API Service
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: finbot-app
    hostname: finbot-app
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql+psycopg2://finbot:finbot_secure_pwd@postgres:5432/finbot_db
      - DEBUG=False
      - LOG_LEVEL=INFO
      - ENVIRONMENT=production
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    networks:
      - finbot-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Redis Cache Service
  redis:
    image: redis:7-alpine
    container_name: finbot-redis
    hostname: redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --requirepass finbot_redis_pwd --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks:
      - finbot-network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "2"

  # PostgreSQL Database Service
  postgres:
    image: postgres:15-alpine
    container_name: finbot-postgres
    hostname: postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: finbot
      POSTGRES_PASSWORD: finbot_secure_pwd
      POSTGRES_DB: finbot_db
      POSTGRES_INITDB_ARGS: "-c shared_buffers=256MB -c max_connections=200"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./docker/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - finbot-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finbot -d finbot_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: finbot-nginx
    hostname: nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    networks:
      - finbot-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  postgres-data:
    driver: local
  redis-data:
    driver: local

networks:
  finbot-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16

================================================================================
3. .dockerignore (30 LOC)
================================================================================

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.pytest_cache/

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Git
.git
.gitignore
.gitattributes

# CI/CD
.github/
.gitlab-ci.yml
.travis.yml

# Development
.env
.env.local
.env.*.local
docker-compose.override.yml

# Data/Logs (keep in volume)
# logs/ (handled by volume mount)
# data/ (handled by volume mount)

# Tests
tests/
.pytest_cache/
htmlcov/

# Build
build/
dist/
*.egg-info/
*.egg

# OS
*.DS_Store
Thumbs.db

================================================================================
4. docker/.env.example (40 LOC)
================================================================================

# ===== APPLICATION CONFIG =====

# Environment
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO

# ===== DATABASE CONFIG =====

# PostgreSQL
DATABASE_URL=postgresql+psycopg2://finbot:finbot_secure_pwd@postgres:5432/finbot_db
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_ECHO=False

# ===== CACHE CONFIG =====

# Redis
REDIS_URL=redis://:finbot_redis_pwd@redis:6379/0
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# ===== API CONFIG =====

API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_TIMEOUT=120

# ===== LOGGING CONFIG =====

LOG_LEVEL=INFO
LOG_FORMAT=json

# ===== SECRETS (CHANGE IN PRODUCTION!) =====

POSTGRES_PASSWORD=finbot_secure_pwd
REDIS_PASSWORD=finbot_redis_pwd
SECRET_KEY=your-secret-key-change-in-production

# ===== FEATURE FLAGS =====

ENABLE_SENTIMENT_ANALYSIS=true
ENABLE_ML_PREDICTIONS=true
ENABLE_BACKTESTING=true
ENABLE_WALK_FORWARD=true

# ===== EXTERNAL APIS (optional) =====

NEWSAPI_KEY=your-newsapi-key
YFINANCE_API_KEY=your-yfinance-key
```

====================================================================================
5. docker/nginx.conf (100 LOC) - Reverse proxy + load balancing
====================================================================================

\"\"\"
Nginx configuration for FinBot API gateway

Features:
- Reverse proxy to FastAPI backend
- Gzip compression
- Rate limiting
- Security headers
- Health check endpoint
\"\"\"

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] \"$request\" '
                    '$status $body_bytes_sent \"$http_referer\" '
                    '\"$http_user_agent\" \"$http_x_forwarded_for\"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/javascript application/json;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=backtest_limit:10m rate=1r/s;

    # Upstream backend
    upstream finbot_backend {
        least_conn;
        server app:8000 max_fails=3 fail_timeout=30s;
    }

    server {
        listen 80;
        server_name _;
        client_max_body_size 10M;

        # Security headers
        add_header X-Frame-Options \"SAMEORIGIN\" always;
        add_header X-Content-Type-Options \"nosniff\" always;
        add_header X-XSS-Protection \"1; mode=block\" always;
        add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;

        # Health check endpoint (no rate limit)
        location /health {
            access_log off;
            proxy_pass http://finbot_backend;
        }

        # Backtest endpoints (strict rate limit)
        location ~ ^/api/backtest/ {
            limit_req zone=backtest_limit burst=2 nodelay;
            proxy_pass http://finbot_backend;
            include proxy_params;
        }

        # API endpoints (standard rate limit)
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://finbot_backend;
            include proxy_params;
        }

        # Root
        location / {
            proxy_pass http://finbot_backend;
            include proxy_params;
        }
    }
}

================================================================================
6. docker/init-db.sql (60 LOC) - Database initialization
================================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS uuid-ossp;

-- Tables are created by SQLAlchemy models via alembic
-- This script just ensures proper initialization

-- Create schema
CREATE SCHEMA IF NOT EXISTS finbot;

-- Ensure proper permissions
GRANT USAGE ON SCHEMA finbot TO finbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA finbot GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO finbot;

-- Create audit table (optional)
CREATE TABLE IF NOT EXISTS finbot.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(255),
    operation VARCHAR(10),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255)
);

-- Index for performance
CREATE INDEX idx_audit_table_time ON finbot.audit_log(table_name, changed_at DESC);

================================================================================
7. docker/README.md (150 LOC) - Complete documentation
================================================================================

# 🐳 FinBot Docker Setup

Complete Docker environment for FinBot trading engine.

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/yourorg/finbot.git
cd finbot

# 2. Copy environment file
cp docker/.env.example docker/.env

# 3. IMPORTANT: Change passwords in docker/.env
vi docker/.env

# 4. Build and start services
docker-compose up -d

# 5. Verify services
docker-compose ps
docker-compose logs -f app

# 6. Health check
curl http://localhost/health
```

## Services

### App (FastAPI)
- Port: 8000 (internal), 80 (external via nginx)
- Health: GET /health
- API Docs: GET /docs
- Container: finbot-app

### Redis Cache
- Port: 6379
- Password: finbot_redis_pwd (change in .env!)
- Max Memory: 512MB with LRU eviction
- Container: finbot-redis

### PostgreSQL Database
- Port: 5432
- User: finbot
- Password: finbot_secure_pwd (change in .env!)
- Database: finbot_db
- Container: finbot-postgres

### Nginx Reverse Proxy
- Port: 80
- Features: Rate limiting, compression, security headers
- Container: finbot-nginx

## Development Mode

```bash
# With live reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or manually run locally (faster iteration)
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://finbot:finbot@localhost:5432/finbot_db
export REDIS_URL=redis://localhost:6379/0
python -m financial_analyzer.api.main
```

## Production Deployment

```bash
# 1. Update .env with production values
# 2. Use production docker-compose
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Setup SSL certificates
# 4. Configure backup strategy
# 5. Setup monitoring (Phase 5.7.3)
```

## Common Tasks

### View logs
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis

### Backup database
docker exec finbot-postgres pg_dump -U finbot finbot_db > backup.sql

### Restore database
cat backup.sql | docker exec -i finbot-postgres psql -U finbot -d finbot_db

### Clean everything
docker-compose down -v  # WARNING: Deletes all data!

### Rebuild image
docker-compose build --no-cache app

## Troubleshooting

### App can't connect to Redis
- Check Redis is running: docker-compose ps redis
- Check password in .env matches docker-compose.yml
- Test: docker exec finbot-redis redis-cli ping

### App can't connect to PostgreSQL
- Check postgres is running: docker-compose ps postgres
- Check password in .env
- Test: docker exec finbot-postgres psql -U finbot -d finbot_db -c \"SELECT 1\"

### Nginx returns 502 Bad Gateway
- Check app is running: docker-compose logs app
- Check app health: curl http://localhost:8000/health
- Check nginx config: docker-compose logs nginx

## Performance Tuning

### Increase app workers
Edit docker-compose.yml, app.environment: API_WORKERS=8 (for powerful servers)

### Increase database connections
Edit docker-compose.yml, postgres.environment: POSTGRES_INITDB_ARGS

### Increase redis memory
Edit docker-compose.yml, redis.command: --maxmemory 1gb

## Security Checklist

- [ ] Change all passwords in .env
- [ ] Use environment-specific .env files
- [ ] Enable HTTPS in production (nginx)
- [ ] Use secrets manager for sensitive data
- [ ] Setup firewall rules
- [ ] Regular security updates
- [ ] Monitor access logs

================================================================================
REQUIREMENTS
================================================================================

✅ Multi-stage Dockerfile (optimized image size)
✅ Non-root user (security best practice)
✅ Health checks on all services
✅ Proper logging configuration
✅ Environment separation (dev vs prod)
✅ Security headers + SSL ready
✅ Rate limiting + compression
✅ Graceful shutdown (tini)
✅ Data persistence (volumes)
✅ Network isolation (custom bridge)
✅ Connection pooling configured
✅ Redis with LRU eviction
✅ PostgreSQL with indexes
✅ Comprehensive documentation
✅ Production-ready (100% quality)

CRITICAL:
- All passwords MUST be changed in .env
- Multi-stage build for minimal image size (~500MB)
- Health checks prevent unhealthy containers
- Rate limiting on API endpoints
- Gzip compression for bandwidth
- Structured logging for monitoring
```

---

## 📋 QUICK CHECKLIST

**Fichiers à générer** :
1. ✅ Dockerfile (80 LOC)
2. ✅ docker-compose.yml (120 LOC)
3. ✅ .dockerignore (30 LOC)
4. ✅ docker/.env.example (40 LOC)
5. ✅ docker/nginx.conf (100 LOC)
6. ✅ docker/init-db.sql (60 LOC)
7. ✅ docker/README.md (150 LOC)

**Total** : ~580 LOC

---

## 📊 EXPECTED DELIVERABLES

```
✅ Dockerfile (multi-stage, optimized, secure)
✅ docker-compose.yml (4 services orchestrated)
✅ .dockerignore (optimize image size)
✅ .env.example (all config options documented)
✅ nginx.conf (reverse proxy + security)
✅ init-db.sql (database initialization)
✅ README.md (complete guide + troubleshooting)

Total Size: ~580 LOC
Quality: PRODUCTION-READY 🚀
```

---

## ⚠️ CRITICAL REQUIREMENTS

1. **Multi-stage build** - Image must be <600MB
2. **Non-root user** - Security mandatory
3. **Health checks** - All services monitored
4. **Graceful shutdown** - tini for signal handling
5. **Logging** - Structured JSON logs
6. **Documentation** - Complete + examples
7. **Security headers** - HSTS, CSP, X-Frame-Options
8. **Rate limiting** - Backtest: 1r/s, API: 10r/s

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀

**C'est Phase 5.7.1 - Docker Setup - QUALITÉ MAXIMUM!** 🎯

**Temps estimé par Copilot : 3-4 heures (avec qualité)** ⏱️

**Livraison cible** : Dimanche 9 novembre, ~22h

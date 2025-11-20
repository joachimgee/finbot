# 🐳 FinBot Docker Setup

Complete Docker environment for the FinBot algorithmic trading platform.

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Services](#services)
- [Development Mode](#development-mode)
- [Production Deployment](#production-deployment)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Security Checklist](#security-checklist)

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available
- 10GB+ disk space

### Installation

```bash
# 1. Clone repository
git clone https://github.com/joachimgee/finbot.git
cd finbot

# 2. Copy environment file
cp docker/.env.example docker/.env

# 3. ⚠️ IMPORTANT: Change passwords in docker/.env
nano docker/.env
# Update: POSTGRES_PASSWORD, REDIS_PASSWORD, SECRET_KEY

# 4. Create volume directories
mkdir -p docker/volumes/postgres docker/volumes/redis logs data

# 5. Build and start services
docker-compose up -d

# 6. Verify services are running
docker-compose ps

# 7. Check logs
docker-compose logs -f app

# 8. Health check
curl http://localhost/health

# 9. Access API documentation
open http://localhost/docs
```

### Expected Output

```bash
$ docker-compose ps
NAME                COMMAND                  STATUS          PORTS
finbot-app          "gunicorn --bind 0.0…"   Up (healthy)    0.0.0.0:8000->8000/tcp
finbot-nginx        "nginx -g 'daemon of…"   Up (healthy)    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
finbot-postgres     "docker-entrypoint.s…"   Up (healthy)    0.0.0.0:5432->5432/tcp
finbot-redis        "redis-server --requ…"   Up (healthy)    0.0.0.0:6379->6379/tcp
```

---

## 🔧 Services

### 1. App (FastAPI Backend)

**Purpose**: Main FinBot API service

**Details**:
- **Image**: `finbot:latest` (built from Dockerfile)
- **Port**: 8000 (internal), 80 (external via nginx)
- **Health**: `GET /health`
- **API Docs**: `GET /docs` or `GET /redoc`
- **Workers**: 4 Gunicorn workers with Uvicorn
- **Container**: `finbot-app`

**Endpoints**:
- `/health` - Health check
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI
- `/api/v1/*` - API routes

### 2. Redis (Cache)

**Purpose**: Caching layer for market data and session storage

**Details**:
- **Image**: `redis:7-alpine`
- **Port**: 6379
- **Password**: `finbot_redis_pwd` (⚠️ change in .env!)
- **Max Memory**: 512MB with LRU eviction
- **Persistence**: AOF + RDB snapshots
- **Container**: `finbot-redis`

**Configuration**:
- Eviction policy: `allkeys-lru`
- Persistence: Append-only file + snapshots
- Snapshots: 900s/1, 300s/10, 60s/10000

### 3. PostgreSQL (Database)

**Purpose**: Primary data store for backtests, portfolios, and analytics

**Details**:
- **Image**: `postgres:15-alpine`
- **Port**: 5432
- **User**: `finbot`
- **Password**: `finbot_secure_pwd` (⚠️ change in .env!)
- **Database**: `finbot_db`
- **Container**: `finbot-postgres`

**Features**:
- Extensions: `pg_trgm`, `uuid-ossp`, `btree_gin`, `btree_gist`
- Schema: `finbot`
- Audit logging enabled
- Performance monitoring views

### 4. Nginx (Reverse Proxy)

**Purpose**: Reverse proxy, load balancer, rate limiter

**Details**:
- **Image**: `nginx:alpine`
- **Port**: 80 (HTTP), 443 (HTTPS ready)
- **Container**: `finbot-nginx`

**Features**:
- Rate limiting: API (10r/s), Backtest (1r/s), WFA (1r/5s)
- Gzip compression
- Security headers (X-Frame-Options, CSP, etc.)
- Load balancing (least_conn)
- WebSocket support

---

## 🛠️ Development Mode

### Local Development (without Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start only database services
docker-compose up -d postgres redis

# 3. Set environment variables
export DATABASE_URL=postgresql+psycopg2://finbot:finbot_secure_pwd@localhost:5432/finbot_db
export REDIS_URL=redis://:finbot_redis_pwd@localhost:6379/0
export DEBUG=True
export LOG_LEVEL=DEBUG

# 4. Run app locally with hot reload
uvicorn financial_analyzer.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Development Docker Compose

Create `docker-compose.dev.yml`:

```yaml
version: '3.9'

services:
  app:
    volumes:
      - .:/app  # Mount source code for hot reload
    environment:
      - DEBUG=True
      - LOG_LEVEL=DEBUG
    command: uvicorn financial_analyzer.api.main:app --reload --host 0.0.0.0 --port 8000
```

Run with:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## 🚀 Production Deployment

### Pre-Deployment Checklist

- [ ] Update all passwords in `.env`
- [ ] Set `DEBUG=False` in `.env`
- [ ] Configure SSL certificates
- [ ] Set up backup strategy
- [ ] Configure monitoring (Sentry, Prometheus)
- [ ] Review security settings
- [ ] Test health checks
- [ ] Configure log rotation
- [ ] Set up firewall rules

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.9'

services:
  app:
    restart: always
    environment:
      - ENVIRONMENT=production
      - DEBUG=False
      - LOG_LEVEL=WARNING
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

Deploy:

```bash
# 1. Build production image
docker-compose build --no-cache

# 2. Start production stack
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verify services
docker-compose ps
docker-compose logs -f

# 4. Test health
curl https://your-domain.com/health
```

### SSL/TLS Configuration

1. Obtain SSL certificates (Let's Encrypt recommended):

```bash
# Install certbot
apt-get install certbot

# Generate certificates
certbot certonly --standalone -d finbot.ai -d www.finbot.ai

# Copy certificates
cp /etc/letsencrypt/live/finbot.ai/fullchain.pem docker/ssl/cert.pem
cp /etc/letsencrypt/live/finbot.ai/privkey.pem docker/ssl/key.pem
```

2. Uncomment HTTPS server block in `docker/nginx.conf`

3. Restart nginx:

```bash
docker-compose restart nginx
```

---

## 📚 Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f nginx

# Last 100 lines
docker-compose logs --tail=100 app

# Filter by timestamp
docker-compose logs --since 2024-01-01T00:00:00 app
```

### Database Management

#### Backup Database

```bash
# Backup to file
docker exec finbot-postgres pg_dump -U finbot finbot_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
docker exec finbot-postgres pg_dump -U finbot finbot_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

#### Restore Database

```bash
# From SQL file
cat backup.sql | docker exec -i finbot-postgres psql -U finbot -d finbot_db

# From compressed file
gunzip -c backup.sql.gz | docker exec -i finbot-postgres psql -U finbot -d finbot_db
```

#### Access Database Shell

```bash
docker exec -it finbot-postgres psql -U finbot -d finbot_db
```

### Redis Management

#### Access Redis CLI

```bash
docker exec -it finbot-redis redis-cli -a finbot_redis_pwd
```

#### Common Redis Commands

```bash
# Check connection
docker exec finbot-redis redis-cli -a finbot_redis_pwd ping

# Monitor commands
docker exec finbot-redis redis-cli -a finbot_redis_pwd monitor

# View info
docker exec finbot-redis redis-cli -a finbot_redis_pwd info

# Flush all data (⚠️ destructive!)
docker exec finbot-redis redis-cli -a finbot_redis_pwd flushall
```

### Container Management

#### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart app
```

#### Stop Services

```bash
# Stop all
docker-compose stop

# Stop specific service
docker-compose stop app
```

#### Remove Everything

```bash
# Stop and remove containers (keeps volumes)
docker-compose down

# Remove containers and volumes (⚠️ data loss!)
docker-compose down -v
```

#### Rebuild Image

```bash
# Rebuild with no cache
docker-compose build --no-cache app

# Rebuild and restart
docker-compose up -d --build app
```

### Monitoring

#### Check Resource Usage

```bash
docker stats
```

#### Check Container Health

```bash
docker inspect finbot-app --format='{{.State.Health.Status}}'
```

---

## 🔍 Troubleshooting

### App Can't Connect to Redis

**Symptoms**: `ConnectionError: Error connecting to Redis`

**Solutions**:

1. Check Redis is running:
```bash
docker-compose ps redis
```

2. Verify password in `.env` matches `docker-compose.yml`

3. Test connection:
```bash
docker exec finbot-redis redis-cli -a finbot_redis_pwd ping
# Should return: PONG
```

4. Check Redis logs:
```bash
docker-compose logs redis
```

### App Can't Connect to PostgreSQL

**Symptoms**: `OperationalError: could not connect to server`

**Solutions**:

1. Check Postgres is running:
```bash
docker-compose ps postgres
```

2. Verify credentials in `.env`

3. Test connection:
```bash
docker exec finbot-postgres psql -U finbot -d finbot_db -c "SELECT 1"
# Should return: 1
```

4. Check Postgres logs:
```bash
docker-compose logs postgres
```

### Nginx Returns 502 Bad Gateway

**Symptoms**: HTTP 502 when accessing API

**Solutions**:

1. Check app is running:
```bash
docker-compose ps app
docker-compose logs app
```

2. Test app health directly:
```bash
curl http://localhost:8000/health
```

3. Check nginx config:
```bash
docker exec finbot-nginx nginx -t
```

4. Check nginx logs:
```bash
docker-compose logs nginx
```

### Out of Disk Space

**Symptoms**: Various failures, "no space left on device"

**Solutions**:

1. Check disk usage:
```bash
df -h
docker system df
```

2. Clean up:
```bash
# Remove unused containers/images
docker system prune -a

# Remove old logs
find logs/ -name "*.log" -mtime +30 -delete
```

3. Adjust log rotation in `docker-compose.yml`:
```yaml
logging:
  options:
    max-size: "5m"  # Reduce from 10m
```

### Container Keeps Restarting

**Symptoms**: Container status shows "Restarting"

**Solutions**:

1. Check logs for errors:
```bash
docker-compose logs app
```

2. Disable restart to debug:
```bash
docker-compose stop app
docker-compose run --rm app bash
```

3. Check health check:
```bash
docker inspect finbot-app --format='{{json .State.Health}}'
```

---

## ⚡ Performance Tuning

### Increase App Workers

For powerful servers (8+ CPU cores):

```yaml
# docker-compose.yml
environment:
  - API_WORKERS=8  # Increase from 4
```

Or in Dockerfile:

```dockerfile
CMD ["gunicorn", "--workers", "8", ...]
```

### Increase Database Connections

```yaml
# docker-compose.yml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c shared_buffers=512MB -c max_connections=400"
```

### Increase Redis Memory

```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 1gb ...
```

### Optimize Docker

```bash
# Enable BuildKit for faster builds
export DOCKER_BUILDKIT=1

# Use BuildKit cache
docker-compose build --build-arg BUILDKIT_INLINE_CACHE=1
```

### Monitor Performance

```bash
# Real-time stats
docker stats

# Resource usage
docker system df -v

# Database stats
docker exec finbot-postgres psql -U finbot -d finbot_db -c "SELECT * FROM finbot.database_stats"
```

---

## 🔒 Security Checklist

### Before Production

- [ ] **Change all default passwords** in `.env`
- [ ] Use environment-specific `.env` files (dev/staging/prod)
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Use secrets manager for sensitive data (AWS Secrets Manager, Vault)
- [ ] Set up firewall rules (allow only 80/443)
- [ ] Enable security headers in nginx
- [ ] Regular security updates (`docker-compose pull`)
- [ ] Monitor access logs for suspicious activity
- [ ] Implement intrusion detection (Fail2Ban)
- [ ] Set up automated backups
- [ ] Test disaster recovery procedures
- [ ] Enable audit logging
- [ ] Restrict database access to internal network
- [ ] Use read-only volumes where possible
- [ ] Implement rate limiting (already configured)
- [ ] Set up alerting for failed health checks

### Security Best Practices

```bash
# 1. Scan images for vulnerabilities
docker scan finbot:latest

# 2. Update base images regularly
docker-compose pull
docker-compose up -d --build

# 3. Use Docker secrets (Swarm mode)
echo "your_secret" | docker secret create db_password -

# 4. Limit container resources
docker-compose config --resolve-image-digests
```

---

## 📞 Support

For issues or questions:
- GitHub Issues: https://github.com/joachimgee/finbot/issues
- Documentation: https://github.com/joachimgee/finbot/blob/main/README.md

---

## 📝 License

See [LICENSE](../LICENSE) file.

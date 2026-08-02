#!/usr/bin/env bash
# Deployment script for FinBot
# Usage: ./scripts/deploy.sh [staging|production]
# Requires: docker, docker-compose

set -euo pipefail

ENVIRONMENT=${1:-staging}
REGISTRY=ghcr.io
IMAGE_OWNER=${IMAGE_OWNER:-joachimgee}
IMAGE_NAME=${IMAGE_NAME:-finbot}
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE_REF="${REGISTRY}/${IMAGE_OWNER}/${IMAGE_NAME}:${IMAGE_TAG}"
DOCKER_COMPOSE_FILE="docker-compose.yml"
MAX_HEALTH_RETRIES=30
SLEEP_SECONDS=5

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
error() { log "ERROR: $*" >&2; exit 1; }

if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
  error "Invalid environment: $ENVIRONMENT (use staging|production)"
fi

log "Starting deployment to $ENVIRONMENT"

# Pre-flight checks
command -v docker >/dev/null 2>&1 || error "docker not installed"
command -v docker-compose >/dev/null 2>&1 || error "docker-compose not installed"

log "Pulling image $IMAGE_REF"
docker pull "$IMAGE_REF" || error "Failed to pull image $IMAGE_REF"

# Optional test discovery (lightweight)
log "Verifying tests presence in image"
docker run --rm "$IMAGE_REF" python -m pytest --co -q || log "Warning: could not enumerate tests inside image"

# Backup existing state (if present)
if [[ -d backups ]]; then
  TS=$(date +%s)
  log "Creating backup snapshot backups.${TS}"
  cp -r backups "backups.${TS}" || log "Backup creation failed (continuing)"
fi

log "Stopping current services"
docker-compose -f "$DOCKER_COMPOSE_FILE" down || log "Warning: docker-compose down returned non-zero"

log "Starting new services"
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d || error "Compose up failed"

log "Running health check loop"
for i in $(seq 1 "$MAX_HEALTH_RETRIES"); do
  if docker-compose exec -T app curl -fsS http://localhost:8000/health >/dev/null; then
    log "Health check passed on attempt $i"
    HEALTH_OK=1
    break
  fi
  log "Waiting for healthy service ($i/$MAX_HEALTH_RETRIES)"
  sleep "$SLEEP_SECONDS"
done

if [[ "${HEALTH_OK:-0}" != "1" ]]; then
  error "Health check failed after $MAX_HEALTH_RETRIES attempts"
fi

log "Deployment to $ENVIRONMENT completed successfully"

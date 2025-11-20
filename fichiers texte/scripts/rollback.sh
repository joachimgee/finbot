#!/usr/bin/env bash
# Rollback script for FinBot
# Usage: ./scripts/rollback.sh <backup_timestamp>
# Example: ./scripts/rollback.sh 1731098452

set -euo pipefail

BACKUP_TS=${1:-}
DOCKER_COMPOSE_FILE="docker-compose.yml"
MAX_HEALTH_RETRIES=30
SLEEP_SECONDS=5

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
error() { log "ERROR: $*" >&2; exit 1; }

if [[ -z "$BACKUP_TS" ]]; then
  error "Missing backup timestamp argument"
fi

BACKUP_DIR="backups.$BACKUP_TS"
if [[ ! -d "$BACKUP_DIR" ]]; then
  error "Backup directory $BACKUP_DIR not found"
fi

log "Initiating rollback to snapshot $BACKUP_DIR"

command -v docker >/dev/null 2>&1 || error "docker not installed"
command -v docker-compose >/dev/null 2>&1 || error "docker-compose not installed"

log "Stopping current services"
docker-compose -f "$DOCKER_COMPOSE_FILE" down || log "Warning: services already stopped"

log "Restoring files from $BACKUP_DIR"
cp -r "$BACKUP_DIR"/* . || error "Failed to restore backup contents"

log "Starting services"
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d || error "Compose up failed after rollback"

log "Running post-rollback health checks"
for i in $(seq 1 "$MAX_HEALTH_RETRIES"); do
  if docker-compose exec -T app curl -fsS http://localhost:8000/health >/dev/null; then
    log "Rollback health check passed on attempt $i"
    HEALTH_OK=1
    break
  fi
  log "Waiting for healthy service ($i/$MAX_HEALTH_RETRIES)"
  sleep "$SLEEP_SECONDS"
done

if [[ "${HEALTH_OK:-0}" != "1" ]]; then
  error "Health check failed after rollback"
fi

log "Rollback to $BACKUP_TS completed successfully"

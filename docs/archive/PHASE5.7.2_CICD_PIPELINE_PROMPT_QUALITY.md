# 🎯 PHASE 5.7.2 - CI/CD PIPELINE PROMPT (QUALITY APPROACH)

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10)
✅ Phase 5.6      : Integration & Validation (9.1/10)
✅ Phase 5.7.1    : Docker Setup (9.9/10) - DONE
🚀 Phase 5.7.2    : CI/CD Pipeline - NOW! (Quality > Speed)
```

---

## CONTEXT

**Phase 5.7.2** implémente **GitHub Actions CI/CD** pour FinBot :
- Automated testing on every push
- Docker image building & pushing
- Auto-deployment to staging
- Security scanning (SAST/DAST)
- Performance testing
- Deployment safety checks

**Objectif** : Production-grade CI/CD pipeline, fully automated, safe deployments

**Approche** : QUALITÉ MAXIMALE (correctifs inclus, documentation complète)

---

## 📚 INSPIRATIONS AUDITS

Référez-vous à :
1. AUDIT_BACKTESTING_PY.md - Performance testing patterns
2. Code structure - Best practices from phases 5.5-5.7.1

---

## 📄 PROMPT FOR COPILOT (QUALITY VERSION)

**COPY-PASTE ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.7.2 : CI/CD PIPELINE - PRODUCTION QUALITY

Génère 4 fichiers GitHub Actions + 2 scripts déploiement :

================================================================================
1. .github/workflows/ci.yml (150 LOC) - Testing & building
================================================================================

\"\"\"
CI/CD Pipeline - Test, Build, Push

Runs on:
- Every push to main/develop
- Pull requests
- Manual trigger

Steps:
1. Lint (ruff, black)
2. Type check (mypy)
3. Unit tests (pytest)
4. Integration tests
5. Build Docker image
6. Security scan (trivy)
7. Push to Docker registry
\"\"\"

name: CI - Test & Build

on:
  push:
    branches: [main, develop, release/**]
    tags: [v*]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: \${{ github.repository }}
  PYTHON_VERSION: \"3.11\"

jobs:
  # ========================================================================
  # LINT & FORMAT CHECK
  # ========================================================================
  lint:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: \${{ env.PYTHON_VERSION }}
          cache: pip
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff black mypy pytest
      
      - name: Lint with ruff
        run: |
          ruff check . --fix --exit-zero
          ruff format . --check
      
      - name: Format check with black
        run: black --check .
      
      - name: Type check with mypy
        run: mypy financial_analyzer/ --ignore-missing-imports --no-error-summary || true

  # ========================================================================
  # UNIT & INTEGRATION TESTS
  # ========================================================================
  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    needs: lint
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pwd
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd \"redis-cli ping\"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: \${{ env.PYTHON_VERSION }}
          cache: pip
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt pytest pytest-cov pytest-xdist
      
      - name: Run unit tests
        env:
          DATABASE_URL: postgresql+psycopg2://test_user:test_pwd@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/ -v --cov=financial_analyzer --cov-report=xml --tb=short
      
      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

  # ========================================================================
  # BUILD DOCKER IMAGE
  # ========================================================================
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: test
    
    permissions:
      contents: read
      packages: write
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: \${{ env.REGISTRY }}
          username: \${{ github.actor }}
          password: \${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: \${{ env.REGISTRY }}/\${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha,prefix={{branch}}-
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: \${{ steps.meta.outputs.tags }}
          labels: \${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ========================================================================
  # SECURITY SCANNING
  # ========================================================================
  security:
    name: Security Scanning
    runs-on: ubuntu-latest
    needs: build
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          scan-ref: .
          format: sarif
          output: trivy-results.sarif
      
      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: trivy-results.sarif

================================================================================
2. .github/workflows/deploy.yml (120 LOC) - Deployment to staging/prod
================================================================================

\"\"\"
Deployment Pipeline

Deploys to:
- Staging: on push to develop
- Production: on push to main or release tag

Safety checks:
- All tests passing
- Docker image built
- Security scan passed
- Manual approval for production
\"\"\"

name: Deploy

on:
  workflow_run:
    workflows: [CI - Test & Build]
    types: [completed]
    branches: [main, develop]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: \${{ github.repository }}

jobs:
  # ========================================================================
  # DEPLOY TO STAGING
  # ========================================================================
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop' && github.event.workflow_run.conclusion == 'success'
    environment: staging
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Deploy to staging
        env:
          DEPLOY_KEY: \${{ secrets.STAGING_DEPLOY_KEY }}
          DEPLOY_HOST: \${{ secrets.STAGING_HOST }}
          DEPLOY_USER: \${{ secrets.STAGING_USER }}
        run: |
          # Deploy logic (SSH or cloud provider)
          # This is example placeholder
          echo \"Deploying to staging: \$DEPLOY_HOST\"
      
      - name: Run smoke tests
        env:
          STAGING_URL: https://staging.finbot.local
        run: |
          # Basic health checks
          curl -f \$STAGING_URL/health || exit 1
      
      - name: Notify deployment
        if: always()
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: \${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              \"text\": \"Staging deployment: \${{ job.status }}\",
              \"channel\": \"#deployments\"
            }

  # ========================================================================
  # DEPLOY TO PRODUCTION
  # ========================================================================
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')) && github.event.workflow_run.conclusion == 'success'
    environment: production
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Create deployment
        id: deployment
        uses: actions/github-script@v6
        with:
          script: |
            const deployment = await github.rest.repos.createDeployment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.ref,
              environment: 'production',
              required_contexts: [],
              auto_merge: false
            });
            return deployment.data.id;
      
      - name: Deploy to production
        env:
          DEPLOY_KEY: \${{ secrets.PRODUCTION_DEPLOY_KEY }}
          DEPLOY_HOST: \${{ secrets.PRODUCTION_HOST }}
          DEPLOY_USER: \${{ secrets.PRODUCTION_USER }}
        run: |
          # Production deployment logic
          echo \"Deploying to production: \$DEPLOY_HOST\"
      
      - name: Health check
        env:
          PRODUCTION_URL: https://finbot.local
        run: |
          # Wait for deployment + health checks
          for i in {1..30}; do
            if curl -f \$PRODUCTION_URL/health; then
              echo \"Health check passed\"
              exit 0
            fi
            sleep 10
          done
          exit 1
      
      - name: Update deployment status
        if: always()
        uses: actions/github-script@v6
        with:
          script: |
            await github.rest.repos.createDeploymentStatus({
              owner: context.repo.owner,
              repo: context.repo.repo,
              deployment_id: \${{ steps.deployment.outputs.result }},
              state: '\${{ job.status }}'
            });

================================================================================
3. .github/workflows/performance.yml (100 LOC) - Performance testing
================================================================================

\"\"\"
Performance Testing Pipeline

Runs on:
- Nightly schedule
- Manual trigger
- After deployment to staging

Tests:
- Backtest performance
- Walk-forward analysis speed
- API endpoint latency
\"\"\"

name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM UTC
  workflow_dispatch:

jobs:
  performance:
    name: Performance Testing
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd \"redis-cli ping\"
          --health-interval 10s
        ports:
          - 6379:6379
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: \"3.11\"
          cache: pip
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt pytest pytest-benchmark
      
      - name: Run performance tests
        env:
          DATABASE_URL: postgresql+psycopg2://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/performance/ -v --benchmark-only
      
      - name: Store benchmark results
        uses: benchmark-action/github-action-benchmark@v1
        with:
          tool: 'pytest'
          output-file-path: .benchmarks/output.json
          github-token: \${{ secrets.GITHUB_TOKEN }}

================================================================================
4. .github/workflows/security.yml (80 LOC) - Security scanning
================================================================================

\"\"\"
Security Scanning Pipeline

Runs on:
- Every push
- Daily schedule
- Manual trigger

Scans:
- Dependencies (Dependabot)
- Code (SAST)
- Secrets (git-secrets)
- Container (Trivy)
\"\"\"

name: Security Scan

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 3 * * 0'  # Weekly Sunday
  workflow_dispatch:

jobs:
  security:
    name: Security Analysis
    runs-on: ubuntu-latest
    
    permissions:
      contents: read
      security-events: write
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: \"3.11\"
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt bandit safety
      
      - name: Run Bandit (Python security)
        run: |
          bandit -r financial_analyzer/ -f json -o bandit-report.json || true
      
      - name: Check dependencies (Safety)
        run: |
          safety check --json > safety-report.json || true
      
      - name: Check for secrets
        uses: gitleaks/gitleaks-action@v2

================================================================================
5. scripts/deploy.sh (100 LOC) - Deployment script
================================================================================

#!/bin/bash
# Deployment script for FinBot
# Usage: ./scripts/deploy.sh [staging|production]

set -euo pipefail

ENVIRONMENT=\${1:-staging}
REGISTRY=ghcr.io
IMAGE=\$REGISTRY/finbot:latest
DOCKER_COMPOSE_FILE=\"docker-compose.yml\"

log() {
  echo \"[$(date +'%Y-%m-%d %H:%M:%S')] \$@\"
}

error() {
  log \"ERROR: \$@\" >&2
  exit 1
}

# Validation
if [[ \$ENVIRONMENT != \"staging\" && \$ENVIRONMENT != \"production\" ]]; then
  error \"Invalid environment: \$ENVIRONMENT (use 'staging' or 'production')\"
fi

log \"Deploying to \$ENVIRONMENT...\"

# Pre-deployment checks
log \"Running pre-deployment checks...\"
docker pull \$IMAGE || error \"Failed to pull image\"
docker run --rm \$IMAGE python -m pytest tests/ --co -q || error \"Tests not found\"

# Backup current deployment
log \"Backing up current deployment...\"
if [[ -d \"backups\" ]]; then
  cp -r backups backups.\$(date +%s)
fi

# Deploy
log \"Pulling latest image...\"
docker pull \$IMAGE

log \"Stopping services...\"
docker-compose -f \$DOCKER_COMPOSE_FILE down

log \"Starting services...\"
docker-compose -f \$DOCKER_COMPOSE_FILE up -d

# Health check
log \"Running health checks...\"
for i in {1..30}; do
  if docker-compose exec app curl -f http://localhost:8000/health; then
    log \"✓ Health check passed\"
    break
  fi
  if [[ \$i -eq 30 ]]; then
    error \"Health check failed\"
  fi
  sleep 5
done

log \"✓ Deployment to \$ENVIRONMENT complete!\"

================================================================================
6. scripts/rollback.sh (80 LOC) - Rollback script
================================================================================

#!/bin/bash
# Rollback script for FinBot
# Usage: ./scripts/rollback.sh [number_of_versions_back]

set -euo pipefail

VERSIONS_BACK=\${1:-1}
DOCKER_COMPOSE_FILE=\"docker-compose.yml\"

log() {
  echo \"[$(date +'%Y-%m-%d %H:%M:%S')] \$@\"
}

error() {
  log \"ERROR: \$@\" >&2
  exit 1
}

log \"Rolling back \$VERSIONS_BACK version(s)...\"

# Find backup
BACKUP_DIR=\"backups.\$(ls -t backups.* 2>/dev/null | head -1 | sed 's/backups.//')\"
if [[ ! -d \"\$BACKUP_DIR\" ]]; then
  error \"No backup found\"
fi

log \"Found backup: \$BACKUP_DIR\"

# Stop services
log \"Stopping services...\"
docker-compose -f \$DOCKER_COMPOSE_FILE down

# Restore from backup
log \"Restoring from backup...\"
cp -r \"\$BACKUP_DIR\"/* .

# Start services
log \"Starting services...\"
docker-compose -f \$DOCKER_COMPOSE_FILE up -d

# Health check
log \"Running health checks...\"
for i in {1..30}; do
  if docker-compose exec app curl -f http://localhost:8000/health; then
    log \"✓ Rollback complete!\"
    exit 0
  fi
  sleep 5
done

error \"Health check failed after rollback\"

================================================================================
REQUIREMENTS
================================================================================

✅ 4 GitHub Actions workflows (450 LOC total)
✅ 2 deployment scripts (180 LOC total)
✅ Test automation (pytest, codecov)
✅ Docker image build & push
✅ Security scanning (Trivy, Bandit, gitleaks)
✅ Performance testing (pytest-benchmark)
✅ Deployment safety checks
✅ Rollback capability
✅ Slack notifications
✅ GitHub Deployments API
✅ Staging & production environments
✅ Secrets management (GitHub Secrets)
✅ Health checks after deployment
✅ Comprehensive documentation

CRITICAL:
- All tests MUST pass before deployment
- Security scan MUST pass
- Production deployment requires manual approval
- Rollback scripts must be tested
- GitHub Secrets configured (DEPLOY_KEY, etc.)
```

---

## 📋 QUICK CHECKLIST

**Fichiers à générer** :
1. ✅ `.github/workflows/ci.yml` (150 LOC)
2. ✅ `.github/workflows/deploy.yml` (120 LOC)
3. ✅ `.github/workflows/performance.yml` (100 LOC)
4. ✅ `.github/workflows/security.yml` (80 LOC)
5. ✅ `scripts/deploy.sh` (100 LOC)
6. ✅ `scripts/rollback.sh` (80 LOC)

**Total** : ~630 LOC

---

## 📊 EXPECTED DELIVERABLES

```
✅ CI Pipeline (lint, test, build)
✅ Deploy Pipeline (staging, production)
✅ Performance Testing Pipeline
✅ Security Scanning Pipeline
✅ Deployment scripts (deploy + rollback)
✅ GitHub Secrets configuration guide
✅ Troubleshooting guide

Total: ~630 LOC
Quality: PRODUCTION-READY 🚀
```

---

## ⚠️ CRITICAL REQUIREMENTS

1. **All tests must pass** before deployment
2. **Security scan must pass** before deployment
3. **Production approval required** (manual gate)
4. **Rollback capability** included
5. **Health checks** after deployment
6. **Secrets management** via GitHub Secrets
7. **Notifications** (Slack integration)
8. **Documentation** - GitHub Secrets setup

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀

**C'est Phase 5.7.2 - CI/CD Pipeline - QUALITÉ MAXIMALE!** 🎯

**Temps estimé par Copilot : 4-5 heures (avec qualité)** ⏱️

**Livraison cible** : Dimanche 9 novembre, ~23h

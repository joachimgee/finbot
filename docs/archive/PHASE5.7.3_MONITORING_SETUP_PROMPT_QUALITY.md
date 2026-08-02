# 🎯 PHASE 5.7.3 - MONITORING SETUP PROMPT (QUALITY APPROACH)

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10)
✅ Phase 5.6      : Integration & Validation (9.1/10)
✅ Phase 5.7.1    : Docker Setup (9.9/10) ✅ DONE
✅ Phase 5.7.2    : CI/CD Pipeline (9.7/10) ✅ DONE
🚀 Phase 5.7.3    : Monitoring Setup - NOW! (Quality > Speed)
```

---

## CONTEXT

**Phase 5.7.3** implémente **Prometheus + Grafana Monitoring** pour FinBot :
- Prometheus metrics collection
- Grafana dashboards (trading, performance, system)
- Alerting rules (Alertmanager)
- Service health monitoring
- Performance metrics (latency, throughput, errors)
- Business metrics (trades, P&L, drawdown)

**Objectif** : Production-grade monitoring, real-time visibility, proactive alerting

**Approche** : QUALITÉ MAXIMALE (correctifs inclus, documentation complète)

---

## 📚 INSPIRATIONS AUDITS

Référez-vous à :
1. AUDIT_BACKTESTING_PY.md - Performance patterns
2. Phase 5.6.2 - Performance optimization metrics

---

## 📄 PROMPT FOR COPILOT (QUALITY VERSION)

**COPY-PASTE ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.7.3 : MONITORING SETUP - PRODUCTION QUALITY

Génère 5 fichiers monitoring + 1 documentation :

================================================================================
1. docker-compose.monitoring.yml (120 LOC) - Monitoring stack
================================================================================

\"\"\"
Monitoring & Alerting Stack

Services:
- Prometheus (metric collection & storage)
- Grafana (visualization & dashboards)
- Alertmanager (alerting)
- Node Exporter (system metrics)

Features:
- Scrape FinBot metrics every 15s
- Retention: 15 days
- Alerting rules (CPU, Memory, Errors)
\"\"\"

version: '3.9'

services:
  # ========================================================================
  # PROMETHEUS - Metrics Collection & Storage
  # ========================================================================
  prometheus:
    image: prom/prometheus:latest
    container_name: finbot-prometheus
    hostname: prometheus
    restart: unless-stopped
    
    ports:
      - \"9090:9090\"
    
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - prometheus-data:/prometheus
    
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
      - '--web.enable-lifecycle'
    
    networks:
      - finbot-network
    
    healthcheck:
      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:9090/-/healthy\"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"10m\"
        max-file: \"3\"

  # ========================================================================
  # GRAFANA - Visualization & Dashboards
  # ========================================================================
  grafana:
    image: grafana/grafana:latest
    container_name: finbot-grafana
    hostname: grafana
    restart: unless-stopped
    
    ports:
      - \"3000:3000\"
    
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=finbot_grafana_pwd
      - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3000
    
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
    
    depends_on:
      - prometheus
    
    networks:
      - finbot-network
    
    healthcheck:
      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:3000/api/health\"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 40s
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"10m\"
        max-file: \"3\"

  # ========================================================================
  # ALERTMANAGER - Alert Routing & Notifications
  # ========================================================================
  alertmanager:
    image: prom/alertmanager:latest
    container_name: finbot-alertmanager
    hostname: alertmanager
    restart: unless-stopped
    
    ports:
      - \"9093:9093\"
    
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager-data:/alertmanager
    
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    
    networks:
      - finbot-network
    
    healthcheck:
      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:9093/-/healthy\"]
      interval: 15s
      timeout: 5s
      retries: 3
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"5m\"
        max-file: \"2\"

  # ========================================================================
  # NODE EXPORTER - System Metrics
  # ========================================================================
  node-exporter:
    image: prom/node-exporter:latest
    container_name: finbot-node-exporter
    hostname: node-exporter
    restart: unless-stopped
    
    ports:
      - \"9100:9100\"
    
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    
    networks:
      - finbot-network
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"5m\"
        max-file: \"2\"

volumes:
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
  alertmanager-data:
    driver: local

networks:
  finbot-network:
    driver: bridge

================================================================================
2. monitoring/prometheus.yml (80 LOC) - Prometheus configuration
================================================================================

\"\"\"
Prometheus Configuration

Scrape targets:
- FinBot app (port 8000/metrics)
- Node Exporter (port 9100)

Retention: 15 days
Scrape interval: 15s
\"\"\"

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'finbot-monitor'
    environment: 'production'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - '/etc/prometheus/alert-rules.yml'

scrape_configs:
  # ========================================================================
  # FinBot Application Metrics
  # ========================================================================
  - job_name: 'finbot-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
    
    # Only keep useful labels
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'python_gc_.*'
        action: drop

  # ========================================================================
  # System Metrics
  # ========================================================================
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 30s
    
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'node_network_.*'
        action: drop

  # ========================================================================
  # Docker Metrics (optional)
  # ========================================================================
  - job_name: 'docker'
    static_configs:
      - targets: ['unix_socket']
    unix_socket_path: '/var/run/docker.sock'

================================================================================
3. monitoring/alert-rules.yml (120 LOC) - Alerting rules
================================================================================

\"\"\"
Alert Rules for FinBot

Rules:
- High error rate (>5%)
- High response latency (>1s)
- High memory usage (>80%)
- High CPU usage (>80%)
- FinBot strategy failures
- Database connection issues
- Redis connectivity issues
\"\"\"

groups:
  - name: finbot_alerts
    interval: 15s
    rules:
      # ====================================================================
      # Application Alerts
      # ====================================================================
      
      - alert: HighErrorRate
        expr: rate(finbot_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
          service: finbot-app
        annotations:
          summary: \"High error rate detected on {{ \\$labels.instance }}\"
          description: \"Error rate is {{ \\$value | humanizePercentage }} (threshold: 5%)\"
          dashboard: \"http://localhost:3000/d/finbot-overview\"

      - alert: HighResponseLatency
        expr: histogram_quantile(0.95, finbot_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
          service: finbot-app
        annotations:
          summary: \"High API latency on {{ \\$labels.instance }}\"
          description: \"p95 latency is {{ \\$value | humanizeDuration }}\"

      - alert: BacktestFailure
        expr: rate(finbot_backtest_failures_total[5m]) > 0
        for: 5m
        labels:
          severity: warning
          service: finbot-backtest
        annotations:
          summary: \"Backtest failures detected\"
          description: \"{{ \\$value }} backtest failures in last 5 minutes\"

      - alert: WalkForwardAnalysisFailed
        expr: finbot_wfa_failed_total > 0
        for: 1m
        labels:
          severity: warning
          service: finbot-wfa
        annotations:
          summary: \"Walk-forward analysis failed\"
          description: \"WFA analysis failed on {{ \\$labels.instance }}\"

      # ====================================================================
      # System Alerts
      # ====================================================================
      
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.85
        for: 5m
        labels:
          severity: warning
          service: system
        annotations:
          summary: \"High memory usage on {{ \\$labels.instance }}\"
          description: \"Memory usage is {{ \\$value | humanizePercentage }}\"

      - alert: HighCPUUsage
        expr: (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m]))) > 0.80
        for: 5m
        labels:
          severity: warning
          service: system
        annotations:
          summary: \"High CPU usage on {{ \\$labels.instance }}\"
          description: \"CPU usage is {{ \\$value | humanizePercentage }}\"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{fstype!=\"tmpfs\"} / node_filesystem_size_bytes{fstype!=\"tmpfs\"}) < 0.15
        for: 5m
        labels:
          severity: warning
          service: system
        annotations:
          summary: \"Low disk space on {{ \\$labels.instance }}\"
          description: \"Only {{ \\$value | humanizePercentage }} available\"

      # ====================================================================
      # Database Alerts
      # ====================================================================
      
      - alert: PostgresConnDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
          service: postgres
        annotations:
          summary: \"PostgreSQL connection lost\"
          description: \"Cannot connect to PostgreSQL on {{ \\$labels.instance }}\"

      # ====================================================================
      # Cache Alerts
      # ====================================================================
      
      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
          service: redis
        annotations:
          summary: \"Redis connection lost\"
          description: \"Cannot connect to Redis on {{ \\$labels.instance }}\"

================================================================================
4. monitoring/alertmanager.yml (60 LOC) - Alert routing
================================================================================

\"\"\"
Alertmanager Configuration

Routing:
- Critical alerts → Slack (immediate)
- Warning alerts → Email (hourly)
- All alerts → Web UI

Grouping:
- Group by: service, severity
- Group wait: 10s
- Group interval: 5m
\"\"\"

global:
  resolve_timeout: 5m
  slack_api_url: 'YOUR_SLACK_WEBHOOK_URL'  # Configure via secrets!

templates:
  - '/etc/alertmanager/templates/*.tmpl'

route:
  receiver: 'default'
  group_by: ['service', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 12h

  # ========================================================================
  # Sub-routes by severity
  # ========================================================================
  routes:
    - match:
        severity: critical
      receiver: 'slack-critical'
      group_wait: 5s
      repeat_interval: 1h

    - match:
        severity: warning
      receiver: 'slack-warning'
      group_wait: 30s
      repeat_interval: 4h

    - match:
        service: finbot-app
      receiver: 'finbot-team'
      group_wait: 10s

receivers:
  # ========================================================================
  # Default receiver (summary)
  # ========================================================================
  - name: 'default'
    slack_configs:
      - channel: '#alerts'
        title: '[{{ .GroupLabels.severity }}] {{ .GroupLabels.service }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        send_resolved: true

  # ========================================================================
  # Critical alerts (immediate to Slack)
  # ========================================================================
  - name: 'slack-critical'
    slack_configs:
      - channel: '#critical-alerts'
        title: '🔴 CRITICAL: {{ .GroupLabels.service }}'
        text: |
          Severity: {{ .GroupLabels.severity }}
          {{ range .Alerts }}
          {{ .Annotations.summary }}
          {{ .Annotations.description }}
          {{ end }}
        send_resolved: true

  # ========================================================================
  # Warning alerts (to Slack)
  # ========================================================================
  - name: 'slack-warning'
    slack_configs:
      - channel: '#warnings'
        title: '⚠️ WARNING: {{ .GroupLabels.service }}'
        text: |
          {{ range .Alerts }}
          {{ .Annotations.summary }}
          {{ end }}
        send_resolved: true

  # ========================================================================
  # FinBot team specific
  # ========================================================================
  - name: 'finbot-team'
    slack_configs:
      - channel: '#finbot-ops'
        title: '📊 FinBot Alert'

inhibit_rules:
  # Inhibit warnings if critical alert exists
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['service']

================================================================================
5. monitoring/grafana/provisioning/dashboards.yml (40 LOC) - Dashboard provisioning
================================================================================

\"\"\"
Grafana Dashboard Provisioning

Auto-loads dashboards from:
- /var/lib/grafana/dashboards/*.json
\"\"\"

apiVersion: 1

providers:
  - name: 'FinBot Dashboards'
    orgId: 1
    folder: 'FinBot'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards

================================================================================
6. monitoring/README.md (150 LOC) - Monitoring guide
================================================================================

\"\"\"
Monitoring & Alerting Setup

Components:
- Prometheus: Metrics collection (port 9090)
- Grafana: Visualization (port 3000)
- Alertmanager: Alert routing (port 9093)
- Node Exporter: System metrics

Quick Start:
1. docker-compose -f docker-compose.monitoring.yml up -d
2. Open http://localhost:3000
3. Login: admin / finbot_grafana_pwd
4. Configure Slack webhook in alertmanager.yml

Dashboards:
- Overview (high-level metrics)
- Application Performance (latency, errors, throughput)
- System Metrics (CPU, memory, disk)
- Trading Metrics (trades, P&L, drawdown)
- Backtest Results (win rate, Sharpe, max drawdown)

Alerts:
- Critical: PostgreSQL down, Redis down, high error rate
- Warning: High latency, high memory usage, backtest failure

Metrics Exported by FinBot:
- finbot_errors_total (counter)
- finbot_request_duration_seconds (histogram)
- finbot_backtest_failures_total (counter)
- finbot_trades_total (counter)
- finbot_pnl (gauge)
- finbot_max_drawdown (gauge)

URLs:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Alertmanager: http://localhost:9093
- Node Exporter: http://localhost:9100/metrics
\"\"\"

================================================================================
REQUIREMENTS
================================================================================

✅ Prometheus configuration (scrape, retention, alerting)
✅ Grafana provisioning (dashboards, datasources)
✅ Alertmanager rules (severity-based routing)
✅ System metrics collection (node-exporter)
✅ Slack integration (critical & warning channels)
✅ Health checks (all services)
✅ Volume persistence (data, configs)
✅ Network isolation (finbot-network)
✅ Comprehensive documentation
✅ FinBot metrics exports
✅ Dashboard examples (overview, app, system, trading)
✅ Alert rules (15+ rules)
✅ Playbook documentation

CRITICAL:
- Update SLACK_WEBHOOK_URL in alertmanager.yml
- Configure Grafana admin password
- Set up dashboard JSON files
- Test alerts with test-rule endpoint
- Verify Prometheus scraping targets
```

---

## 📋 QUICK CHECKLIST

**Fichiers à générer** :
1. ✅ `docker-compose.monitoring.yml` (120 LOC)
2. ✅ `monitoring/prometheus.yml` (80 LOC)
3. ✅ `monitoring/alert-rules.yml` (120 LOC)
4. ✅ `monitoring/alertmanager.yml` (60 LOC)
5. ✅ `monitoring/grafana/provisioning/dashboards.yml` (40 LOC)
6. ✅ `monitoring/README.md` (150 LOC)

**Total** : ~570 LOC

---

## 📊 EXPECTED DELIVERABLES

```
✅ Monitoring Stack (Prometheus + Grafana + Alertmanager)
✅ Alert Rules (15+ rules covering system + app + trading)
✅ Dashboard Provisioning (auto-load JSON dashboards)
✅ Slack Integration (critical + warning channels)
✅ System Metrics (CPU, memory, disk, network)
✅ Application Metrics (errors, latency, throughput)
✅ Trading Metrics (trades, P&L, drawdown)
✅ Comprehensive Documentation

Total: ~570 LOC
Quality: PRODUCTION-READY 🚀
```

---

## ⚠️ CRITICAL REQUIREMENTS

1. **Prometheus scrape every 15s** (real-time monitoring)
2. **15-day retention** (balance storage vs history)
3. **Alert routing by severity** (critical → immediate, warning → digest)
4. **Slack webhook integration** (alerting notifications)
5. **Health checks all services** (monitoring monitors monitoring!)
6. **FinBot metrics exports** (must implement app-side)
7. **Dashboard JSON files** (3+ dashboards)
8. **Documentation** (setup + troubleshooting + metrics guide)

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀

**C'est Phase 5.7.3 - Monitoring Setup - QUALITÉ MAXIMALE!** 🎯

**Temps estimé par Copilot : 3-4 heures (avec qualité)** ⏱️

**Livraison cible** : Dimanche 9 novembre, minuit

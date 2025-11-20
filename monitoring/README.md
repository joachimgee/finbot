# Monitoring & Alerting Setup (Phase 5.7.3)

Components:

- **Prometheus**: Metrics collection & storage (port 9090)
- **Grafana**: Visualization & dashboards (port 3000)
- **Alertmanager**: Alert routing (port 9093)
- **Node Exporter**: System metrics (port 9100)

## Quick Start

```bash
docker compose -f docker-compose.monitoring.yml up -d
# Access Grafana:
open http://localhost:3000
```

Login credentials Grafana:

- User: `admin`
- Password: `finbot_grafana_pwd` (change via `GF_SECURITY_ADMIN_PASSWORD`)

Configure Slack webhook:

1. Set environment variable or replace `YOUR_SLACK_WEBHOOK_URL` in `monitoring/alertmanager.yml`.
2. Restart stack: `docker compose -f docker-compose.monitoring.yml restart alertmanager`.

## Dashboards (expected JSON to provision)

Place JSON dashboards in `monitoring/grafana/dashboards/`:

- `overview.json`: High-level service health (uptime, latency, error rate)
- `app_performance.json`: p95/p99 latency, request throughput, error ratio
- `system_metrics.json`: CPU, Memory, Disk, Inodes, Load, Network (filtered)
- `trading_metrics.json`: trades total, P&L, max drawdown, backtest failures
- `backtest_results.json`: Sharpe, win rate, max drawdown, failure count

## Alerts Summary

- Critical: PostgreSQL down, Redis down, high error rate
- Warning: High latency p95/p99, high memory usage, high CPU, drawdown too high, no trading activity

Alert tuning guidelines:

- Use `for:` to avoid flapping (minimum 2-5 minutes stabilization)
- Prefer ratios over absolute counts for error thresholds
- Suppress warnings when critical severity for same service (see inhibit rules)

## Metrics Exported by FinBot (implement in app)

| Metric | Type | Description |
|--------|------|-------------|
| `finbot_errors_total` | counter | Total application errors |
| `finbot_request_duration_seconds` | histogram | Request duration distribution |
| `finbot_backtest_failures_total` | counter | Backtest failure count |
| `finbot_trades_total` | counter | Executed trades count |
| `finbot_pnl` | gauge | Current P&L value |
| `finbot_max_drawdown` | gauge | Current max drawdown |
| `finbot_wfa_failed_total` | counter | Walk-forward analysis failures |

Histogram buckets suggestion:
`finbot_request_duration_seconds_bucket{le="0.1"}, {le="0.25"}, {le="0.5"}, {le="1"}, {le="2"}, {le="5"}`

## Prometheus Configuration

- Scrape interval: 15s (app), 30s (node exporter)
- Retention: 15 days
- Rule evaluation: 15s
- Lifecycle reload: `POST /-/reload` available (enable-lifecycle)

## Alerting Design

- Severity-based routing: critical vs warning channels
- Grouping by `service`, `severity` prevents alert storms
- Inhibition: Warning suppressed if a critical exists for same service
- Repeat intervals prevent spam (critical every 1h, warning every 4h)

## Operations Playbook

| Scenario | Action |
|----------|--------|
| HighErrorRate | Check recent deploy, inspect logs, rollback if sustained |
| HighLatency | Inspect DB/Redis latency, thread pool saturation, GC activity |
| RedisDown | Validate container status, network, credentials |
| PostgresConnDown | Verify exporter & DB availability; failover if multi-node |
| DrawdownTooHigh | Trigger risk management protocol (reduce position sizes) |
| TradingNoActivity | Check market hours / connectivity / strategy hangs |

## Security Considerations

- Do not expose Prometheus/Grafana publicly without auth reverse proxy
- Change default Grafana admin password immediately
- Limit dashboards editing in production (allowUiUpdates = true can be disabled)
- Use network isolation `finbot-network`

## Performance Considerations

- Scrape interval 15s balanced for near real-time latency metrics
- Use metric relabeling to drop verbose GC and network metrics
- Limit histogram buckets to reduce cardinality

## Troubleshooting
| Issue | Cause | Resolution |
|-------|-------|------------|
| Prometheus healthcheck fails | Config syntax error | Check container logs & validate YAML |
| Grafana empty dashboards | Wrong provisioning path | Verify volume mount & provider path |
| Alerts not firing | Rule expression mismatch | Use Prometheus UI /graph to test queries |
| Slack alerts missing | Webhook not set | Configure `slack_api_url` & restart alertmanager |
| High CPU Prometheus | Too many high-cardinality metrics | Drop labels / reduce scrape interval |

## Extending Monitoring
- Add exporters: postgres_exporter, redis_exporter, cadvisor
- Integrate tracing: OpenTelemetry collector (future phase)
- SLO dashboards: availability %, error budget consumption

## Manual Validation Steps
```bash
# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].labels'

# Validate rule groups
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].name'

# Simulate error spike (example) - adapt to app instrumentation
# curl -X POST http://localhost:8000/debug/generate_errors?count=100

# List Grafana datasources (after manual addition)
curl -s http://admin:finbot_grafana_pwd@localhost:3000/api/datasources | jq '.[].name'
```

## Next Steps (Future Phases)
- Add synthetic checks (trading loop heartbeat metric)
- Implement OpenTelemetry traces and span-to-metric conversion
- SLO burn rate alerts (multi-window 5m & 1h)
- Capacity planning dashboards (memory/time series forecasting)

---
Maintainer: FinBot Ops Team
Version: 1.0 (Phase 5.7.3)

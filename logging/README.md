# Centralized Logging Setup (Phase 5.7.4)

Components:

- **Elasticsearch**: Full-text search & storage (port 9200)
- **Logstash**: Log aggregation & transformation (port 5000)
- **Kibana**: Visualization & exploration (port 5601)

## Quick Start

```bash
# 1. Start ELK Stack
docker compose -f docker-compose.logging.yml up -d

# 2. Start main app with logging override
docker compose \
  -f docker-compose.yml \
  -f docker-compose.logging.yml \
  -f logging/docker-compose.logging.override.yml \
  up -d

# 3. Access Kibana
open http://localhost:5601
```

## Initial Setup (First Time)

### Create Index Pattern in Kibana

1. Navigate to **Stack Management** → **Index Patterns**
2. Create pattern: `finbot-*`
3. Select time field: `@timestamp`
4. Save index pattern

## Logging Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| **DEBUG** | Detailed debugging info | Development, troubleshooting |
| **INFO** | General information | Normal operations |
| **WARNING** | Warning messages | Potential issues |
| **ERROR** | Error conditions | Failed operations |
| **CRITICAL** | Critical errors | System failures |

## JSON Log Format

Application should send structured JSON logs to Logstash:

```json
{
  "timestamp": "2025-11-09T00:00:00Z",
  "service": "finbot-app",
  "level": "INFO",
  "request_id": "req-12345",
  "user_id": "user-789",
  "message": "Trade executed",
  "symbol": "AAPL",
  "quantity": 100,
  "price": 150.50,
  "traceback": null
}
```

### Required Fields

- `timestamp`: ISO8601 or UNIX timestamp
- `service`: Service name (finbot-app, postgres, nginx, etc.)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `message`: Human-readable log message

### Optional Fields

- `request_id`: Request correlation ID
- `user_id`: User identifier
- `traceback`: Stack trace for errors
- `error_type`: Exception class name
- Custom fields: symbol, quantity, price, duration, etc.

## Kibana Queries (KQL)

### Common Queries

```kql
# All errors from app
service:finbot-app AND level:ERROR

# Slow requests (>1s)
duration:>1000

# Trades by symbol
event_type:TRADE AND symbol:AAPL

# P&L updates
event_type:PNL_UPDATE

# Specific user activity
user_id:"user-789"

# Time range: Last 15 minutes
@timestamp >= now-15m

# Backtest failures
service:finbot-backtest AND level:ERROR
```

## Dashboard Creation

1. **Create Saved Search**
   - Go to **Discover**
   - Apply filters and query
   - Save search with descriptive name

2. **Create Visualizations**
   - Go to **Visualize**
   - Choose visualization type (line, bar, pie, etc.)
   - Select saved search or index pattern
   - Configure aggregations

3. **Build Dashboard**
   - Go to **Dashboard** → Create new
   - Add saved visualizations
   - Arrange panels
   - Save dashboard

### Recommended Dashboards

- **Overview**: Error rate, request throughput, latency
- **Trading Activity**: Trades per minute, symbols, P&L
- **Errors & Warnings**: Error types, stack traces, affected users
- **Performance**: Request duration, database queries, cache hits

## Index Lifecycle Management (ILM)

Index retention policy (30 days):

- **Hot**: Current day's logs (actively written & searched)
- **Warm**: Last 7 days (searchable, read-only)
- **Cold**: 8-30 days (archived, infrequent access)
- **Delete**: After 30 days (automatically removed)

Daily index rollover: `finbot-YYYY.MM.dd`

### Manual Index Management

```bash
# List indices
curl http://localhost:9200/_cat/indices?v

# Delete old indices (manual cleanup)
curl -X DELETE http://localhost:9200/finbot-2025.10.01

# Check cluster health
curl http://localhost:9200/_cluster/health?pretty
```

## Performance Tuning

### Elasticsearch Heap Size

Adjust `ES_JAVA_OPTS` based on log volume:

- **Low volume** (<1GB/day): `-Xms512m -Xmx512m`
- **Medium volume** (1-10GB/day): `-Xms1g -Xmx1g`
- **High volume** (>10GB/day): `-Xms2g -Xmx2g`

### Logstash Workers

Increase workers for high throughput:

```yaml
environment:
  - "LS_JAVA_OPTS=-Xmx512m -Xms512m"
  - PIPELINE_WORKERS=4  # CPU count
```

### Grok Patterns Usage

The pipeline optionally applies Grok patterns for non-JSON sources using patterns in
`logging/logstash/patterns/grok_patterns`. Ensure the patterns directory is mounted and
update the `grok` match expressions in `logstash.conf` to your log formats if needed.

Test a Grok expression quickly in a dev container:

```bash
echo "GET 200 123ms" | docker exec -i finbot-logstash bash -lc 'cat > /tmp/test.log && logstash -e "input{stdin{}} filter{grok{match=>{"message"=>"%{API_METHOD:http_method} %{API_RESPONSE:http_status} %{API_DURATION:duration}ms"} patterns_dir=>[\"/usr/share/logstash/patterns\"]}} output{stdout{codec=>rubydebug}}" < /tmp/test.log'
```

### Kibana Canvas

For advanced visualizations, use Kibana Canvas for custom dashboards.

## Troubleshooting

| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| Logstash not receiving logs | Check app log config | Verify `LOG_TARGET` env var |
| Elasticsearch unhealthy | Check cluster status | `curl localhost:9200/_cluster/health` |
| Kibana not loading | Check ES connection | Verify `ELASTICSEARCH_HOSTS` |
| No data in Kibana | Index pattern missing | Create `finbot-*` pattern |
| High memory usage ES | Too much heap | Reduce `ES_JAVA_OPTS` or add retention |
| Slow queries | Large time range | Use smaller time windows |

### Log Inspection

```bash
# Check Elasticsearch logs
docker logs finbot-elasticsearch

# Check Logstash logs
docker logs finbot-logstash

# Check Kibana logs
docker logs finbot-kibana

# Test Logstash pipeline
echo '{"message":"test","level":"INFO"}' | nc localhost 5000
```

## Security Considerations

### Production Hardening

- **Enable X-Pack authentication**: Set `xpack.security.enabled=true`
- **Use TLS/SSL**: Encrypt logs in transit
- **Restrict Kibana access**: Use reverse proxy with auth
- **Secrets management**: Store credentials in environment or vault
- **Network segmentation**: Isolate ELK stack network

### Authentication Example

```yaml
elasticsearch:
  environment:
    - xpack.security.enabled=true
    - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
```

## Application Integration

### Python Logging Handler

```python
import logging
import json
import socket

class LogstashHandler(logging.Handler):
    def __init__(self, host='logstash', port=5000):
        super().__init__()
        self.host = host
        self.port = port
    
    def emit(self, record):
        log_entry = {
            'timestamp': record.created,
            'service': 'finbot-app',
            'level': record.levelname,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', None),
            'user_id': getattr(record, 'user_id', None),
        }
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.sendall(json.dumps(log_entry).encode() + b'\n')
            sock.close()
        except Exception:
            pass  # Fail silently

# Usage
logger = logging.getLogger(__name__)
logger.addHandler(LogstashHandler())
logger.info("Trade executed", extra={'symbol': 'AAPL', 'quantity': 100})
```

## URLs

- **Elasticsearch**: http://localhost:9200
- **Logstash**: tcp://localhost:5000 (TCP input)
- **Logstash API**: http://localhost:9600 (Metrics)
- **Kibana**: http://localhost:5601

---

**Maintainer**: FinBot Ops Team  
**Version**: 1.0 (Phase 5.7.4)

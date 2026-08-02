# 🎯 PHASE 5.7.4 - LOGGING INFRASTRUCTURE PROMPT (QUALITY APPROACH)

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10)
✅ Phase 5.6      : Integration & Validation (9.1/10)
✅ Phase 5.7.1    : Docker Setup (9.9/10) ✅ DONE
✅ Phase 5.7.2    : CI/CD Pipeline (9.7/10) ✅ DONE
✅ Phase 5.7.3    : Monitoring Setup (9.7/10) ✅ DONE
🚀 Phase 5.7.4    : Logging Infrastructure - FINAL PHASE! (Quality > Speed)
```

---

## CONTEXT

**Phase 5.7.4** implémente **ELK Stack (Elasticsearch + Logstash + Kibana)** pour FinBot :
- Centralized logging infrastructure
- Elasticsearch pour indexation & storage
- Kibana pour visualization & exploration
- Logstash pour aggregation et transformation
- Application logging best practices
- Log rotation & retention policies

**Objectif** : Production-grade logging, complete audit trail, debugging capability

**Approche** : QUALITÉ MAXIMALE (correctifs inclus, documentation complète)

---

## 📚 INSPIRATIONS AUDITS

Référez-vous à :
1. Phase 5.7.3 - Monitoring stack patterns
2. Code structure - Best practices

---

## 📄 PROMPT FOR COPILOT (QUALITY VERSION)

**COPY-PASTE ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.7.4 : LOGGING INFRASTRUCTURE - PRODUCTION QUALITY

Génère 4 fichiers logging + 1 documentation :

================================================================================
1. docker-compose.logging.yml (100 LOC) - ELK Stack
================================================================================

\"\"\"
ELK Logging Stack for FinBot

Services:
- Elasticsearch (port 9200) - Full-text search & storage
- Logstash (port 5000) - Log aggregation & transformation
- Kibana (port 5601) - Visualization & exploration

Features:
- Centralized logging from all services
- Log indexing by day (finbot-YYYY.MM.DD)
- 30-day retention with hot/warm tiering
- JSON structured logging
- Multi-tenant separation
\"\"\"

version: '3.9'

services:
  # ========================================================================
  # ELASTICSEARCH - Search & Storage
  # ========================================================================
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    container_name: finbot-elasticsearch
    hostname: elasticsearch
    restart: unless-stopped
    
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - xpack.security.enrollment.enabled=false
      - \"ES_JAVA_OPTS=-Xms512m -Xmx512m\"
    
    ulimits:
      memlock:
        soft: -1
        hard: -1
    
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    
    ports:
      - \"9200:9200\"
      - \"9300:9300\"
    
    networks:
      - finbot-network
    
    healthcheck:
      test: [\"CMD-SHELL\", \"curl -f http://localhost:9200/_cluster/health || exit 1\"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 40s
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"10m\"
        max-file: \"3\"

  # ========================================================================
  # LOGSTASH - Log Aggregation & Transformation
  # ========================================================================
  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0
    container_name: finbot-logstash
    hostname: logstash
    restart: unless-stopped
    
    volumes:
      - ./logging/logstash/pipeline:/usr/share/logstash/pipeline:ro
      - ./logging/logstash/patterns:/usr/share/logstash/patterns:ro
    
    environment:
      - \"LS_JAVA_OPTS=-Xmx256m -Xms256m\"
    
    ports:
      - \"5000:5000\"
      - \"9600:9600\"
    
    depends_on:
      elasticsearch:
        condition: service_healthy
    
    networks:
      - finbot-network
    
    command: logstash -f /usr/share/logstash/pipeline/logstash.conf
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"10m\"
        max-file: \"2\"

  # ========================================================================
  # KIBANA - Visualization & Exploration
  # ========================================================================
  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    container_name: finbot-kibana
    hostname: kibana
    restart: unless-stopped
    
    environment:
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    
    ports:
      - \"5601:5601\"
    
    depends_on:
      elasticsearch:
        condition: service_healthy
    
    networks:
      - finbot-network
    
    healthcheck:
      test: [\"CMD-SHELL\", \"curl -f http://localhost:5601/api/status || exit 1\"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    
    logging:
      driver: \"json-file\"
      options:
        max-size: \"5m\"
        max-file: \"2\"

volumes:
  elasticsearch-data:
    driver: local

networks:
  finbot-network:
    driver: bridge

================================================================================
2. logging/logstash/pipeline/logstash.conf (80 LOC) - Logstash pipeline
================================================================================

\"\"\"
Logstash Configuration

Input:
- TCP port 5000 (JSON logs)

Filters:
- JSON parsing
- Field extraction (timestamp, level, service)
- Grok patterns for stack traces

Output:
- Elasticsearch with daily index rollover
\"\"\"

input {
  tcp {
    port => 5000
    codec => json
    type => \"json\"
    host => \"0.0.0.0\"
  }
}

filter {
  # ====================================================================
  # JSON Parsing
  # ====================================================================
  if [type] == \"json\" {
    json {
      source => \"message\"
      target => \"log_data\"
      skip_on_invalid_json => true
    }
  }

  # ====================================================================
  # Field Extraction
  # ====================================================================
  mutate {
    add_field => {
      \"environment\" => \"production\"
      \"version\" => \"1.0.0\"
    }
    
    # Extract key fields
    add_field => {
      \"service\" => \"%{[log_data][service]}\"
      \"level\" => \"%{[log_data][level]}\"
      \"request_id\" => \"%{[log_data][request_id]}\"
      \"user_id\" => \"%{[log_data][user_id]}\"
    }
  }

  # ====================================================================
  # Timestamp Parsing
  # ====================================================================
  if [log_data][timestamp] {
    date {
      match => [\"[log_data][timestamp]\", \"ISO8601\", \"UNIX\"]
      target => \"@timestamp\"
      timezone => \"UTC\"
    }
  }

  # ====================================================================
  # Severity Mapping
  # ====================================================================
  mutate {
    replace => {
      \"severity\" => \"info\"
    }
  }

  if [level] =~ /^ERROR|CRITICAL$/ {
    mutate {
      replace => { \"severity\" => \"error\" }
    }
  } else if [level] == \"WARNING\" {
    mutate {
      replace => { \"severity\" => \"warning\" }
    }
  }

  # ====================================================================
  # Stack Trace Handling
  # ====================================================================
  if [log_data][traceback] {
    mutate {
      add_field => {
        \"has_error\" => true
        \"error_type\" => \"%{[log_data][error_type]}\"
      }
    }
  }

  # ====================================================================
  # Remove verbose fields
  # ====================================================================
  mutate {
    remove_field => [\"message\", \"host\", \"type\"]
  }
}

output {
  # ====================================================================
  # Elasticsearch
  # ====================================================================
  elasticsearch {
    hosts => [\"elasticsearch:9200\"]
    index => \"finbot-%{+YYYY.MM.dd}\"
    document_type => \"_doc\"
  }

  # ====================================================================
  # Console (debug)
  # ====================================================================
  if [severity] == \"error\" {
    stdout {
      codec => rubydebug
    }
  }
}

================================================================================
3. logging/logstash/patterns/grok_patterns (40 LOC) - Grok patterns
================================================================================

\"\"\"
Custom Grok Patterns

Patterns for:
- Stack traces
- API calls
- Trading events
\"\"\"

# API patterns
API_TIMESTAMP %{TIMESTAMP_ISO8601:timestamp}
API_METHOD (?:GET|POST|PUT|DELETE|PATCH)
API_RESPONSE \\d{3}
API_DURATION [\\d.]+

# Trading patterns
TRADE_ACTION (?:BUY|SELL|SHORT)
TRADE_SYMBOL [A-Z0-9]{1,6}
TRADE_PRICE [\\d.]+

# Error patterns
ERROR_TYPE [A-Za-z_]+Error
ERROR_LINE (?:line \\d+)
ERROR_FILE (?:[a-zA-Z0-9_./]+\\.py)

================================================================================
4. logging/docker-compose.logging.override.yml (60 LOC) - App logging config
================================================================================

\"\"\"
Override for main docker-compose.yml
Configures app service to send logs to Logstash

Usage:
docker-compose \\
  -f docker-compose.yml \\
  -f logging/docker-compose.logging.override.yml \\
  up -d
\"\"\"

version: '3.9'

services:
  app:
    # Override logging driver to send to Logstash
    logging:
      driver: \"splunk\"
      options:
        splunk-token: \"${SPLUNK_HEC_TOKEN}\"
        splunk-url: \"http://logstash:5000\"
        tag: \"finbot-app\"
    
    # OR use syslog to Logstash
    # logging:
    #   driver: \"syslog\"
    #   options:
    #     syslog-address: \"tcp://logstash:5000\"
    #     tag: \"finbot-app\"
    
    # OR keep JSON driver, app sends directly to Logstash
    environment:
      - LOG_TARGET=http://logstash:5000
      - LOG_FORMAT=json
      - LOG_LEVEL=INFO

  postgres:
    logging:
      driver: \"json-file\"
      options:
        max-size: \"5m\"
        max-file: \"2\"
        labels: \"service=postgres\"

  redis:
    logging:
      driver: \"json-file\"
      options:
        max-size: \"5m\"
        max-file: \"2\"
        labels: \"service=redis\"

  nginx:
    logging:
      driver: \"json-file\"
      options:
        max-size: \"10m\"
        max-file: \"3\"
        labels: \"service=nginx\"

================================================================================
5. logging/README.md (150 LOC) - Logging guide
================================================================================

\"\"\"
Centralized Logging Setup (Phase 5.7.4)

Components:
- Elasticsearch: Full-text search & storage (port 9200)
- Logstash: Log aggregation (port 5000)
- Kibana: Visualization (port 5601)

Quick Start:

1. Start ELK Stack:
docker-compose -f docker-compose.logging.yml up -d

2. Start main app with logging override:
docker-compose \\
  -f docker-compose.yml \\
  -f logging/docker-compose.logging.override.yml \\
  up -d

3. Access Kibana:
http://localhost:5601

4. Create index pattern:
- Go to Stack Management → Index Patterns
- Create pattern: finbot-*
- Time field: @timestamp

Logging Levels:
- DEBUG: Detailed debugging info
- INFO: General information
- WARNING: Warning messages
- ERROR: Error conditions
- CRITICAL: Critical errors

JSON Log Format (sent to Logstash):
{
  \"timestamp\": \"2025-11-09T00:00:00Z\",
  \"service\": \"finbot-app\",
  \"level\": \"INFO\",
  \"request_id\": \"req-12345\",
  \"user_id\": \"user-789\",
  \"message\": \"Trade executed\",
  \"symbol\": \"AAPL\",
  \"quantity\": 100,
  \"price\": 150.50,
  \"traceback\": null
}

Kibana Queries (KQL):

- All errors:
service:finbot-app AND level:ERROR

- Slow requests (>1s):
duration:>1000

- Trades by symbol:
event_type:TRADE AND symbol:AAPL

- P&L analysis:
event_type:PNL_UPDATE

Dashboard Creation:
1. Create saved search
2. Create visualizations from saved search
3. Combine visualizations in dashboard

Index Lifecycle Management (ILM):
- Hot: Current day's logs
- Warm: Last 7 days (searchable)
- Cold: Older logs (archived)
- Delete: After 30 days

Performance Tuning:
- Elasticsearch heap: 512MB-2GB (based on log volume)
- Logstash workers: CPU count
- Kibana canvas for custom dashboards

Troubleshooting:
- Check Logstash: docker logs finbot-logstash
- Check ES health: curl http://localhost:9200/_cluster/health
- Check Kibana: docker logs finbot-kibana

Security:
- Configure X-Pack authentication
- Use secrets for credentials
- Restrict Kibana access
- Encrypt logs in transit (TLS)
\"\"\"

================================================================================
REQUIREMENTS
================================================================================

✅ ELK Stack complete (Elasticsearch, Logstash, Kibana)
✅ Logstash pipeline configuration (JSON parsing, field extraction)
✅ Custom Grok patterns (stack traces, API calls, trading)
✅ Daily index rollover (finbot-YYYY.MM.dd)
✅ Docker compose override for logging integration
✅ Health checks all services
✅ Volume persistence (elasticsearch-data)
✅ Network isolation (finbot-network)
✅ Comprehensive documentation
✅ Log retention policy (30 days)
✅ Severity-based tagging
✅ Request tracing (request_id)
✅ User tracking (user_id)

CRITICAL:
- Elasticsearch single-node setup (fine for dev/staging)
- Logstash must wait for ES to be healthy
- Daily index rollover for space efficiency
- Kibana index pattern needs manual creation on first run
- JSON structured logging required from app
```

---

## 📋 QUICK CHECKLIST

**Fichiers à générer** :
1. ✅ `docker-compose.logging.yml` (100 LOC)
2. ✅ `logging/logstash/pipeline/logstash.conf` (80 LOC)
3. ✅ `logging/logstash/patterns/grok_patterns` (40 LOC)
4. ✅ `logging/docker-compose.logging.override.yml` (60 LOC)
5. ✅ `logging/README.md` (150 LOC)

**Total** : ~430 LOC

---

## 📊 EXPECTED DELIVERABLES

```
✅ ELK Stack (Elasticsearch + Logstash + Kibana)
✅ Logstash pipeline configuration
✅ Custom Grok patterns (stack traces, API, trading)
✅ Docker compose override (app logging integration)
✅ Daily index rollover (space efficiency)
✅ Health checks (all services monitored)
✅ Volume persistence
✅ Comprehensive documentation

Total: ~430 LOC
Quality: PRODUCTION-READY 🚀
```

---

## ⚠️ CRITICAL REQUIREMENTS

1. **Elasticsearch single-node** (fine for non-mission-critical)
2. **Logstash healthcheck** (wait for ES)
3. **JSON structured logging** from app
4. **Daily index rollover** (finbot-YYYY.MM.dd)
5. **30-day retention** policy
6. **Request/User ID** tracking
7. **Severity tagging** (debug, info, warning, error, critical)
8. **Stack trace capture** (full error context)

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀

**C'est Phase 5.7.4 - Logging Infrastructure - QUALITÉ MAXIMALE!** 🎯

**Temps estimé par Copilot : 2-3 heures (avec qualité)** ⏱️

**Livraison cible** : Dimanche 9 novembre, ~23h45

---

## 🎉 PHASE 5.7 FINALE

Après Phase 5.7.4 : **INFRASTRUCTURE COMPLÈTE!**

```
✅ Phase 5.7.1 : Docker Setup (9.9/10)
✅ Phase 5.7.2 : CI/CD Pipeline (9.7/10)
✅ Phase 5.7.3 : Monitoring Setup (9.7/10)
✅ Phase 5.7.4 : Logging Infrastructure (9.8/10 target)

TOTAL Phase 5.7: ~14 heures
TOTAL Project: ~12,000+ LOC
Quality Average: 9.4/10 (EXCEPTIONAL!)
```

---

**À FAIRE APRÈS PHASE 5.7.4** :
1. Review + Correctifs
2. FINAL DELIVERY REPORT
3. Project complete! 🚀

**LET'S GO! Dernière étape! 💪**

# AvionDash Docker — Datadog Setup Guide

Complete reference for instrumenting AvionDash in Datadog. Covers the Agent, APM, Log Management, Infrastructure Metrics, Monitors, Synthetics, Dashboards, and SLOs.

---

## Prerequisites

- Datadog account (free trial at datadoghq.com works for all features below)
- AvionDash running: `docker compose up -d --build`
- Datadog API key from **Organization Settings → API Keys**

---

## Step 1 — Enable the Datadog Agent

### 1.1 Add your API key to `.env`

```bash
# .env
DD_API_KEY=your_api_key_here
DD_SITE=datadoghq.com   # or datadoghq.eu, us3.datadoghq.com, etc.
```

### 1.2 Uncomment the agent block in `docker-compose.yml`

Find the commented `datadog-agent` service block (at the bottom of the file) and uncomment it. It looks like this when enabled:

```yaml
datadog-agent:
  image: gcr.io/datadoghq/agent:latest
  container_name: aviondash-dd-agent
  restart: unless-stopped
  environment:
    DD_API_KEY:                           ${DD_API_KEY}
    DD_SITE:                              ${DD_SITE:-datadoghq.com}
    DD_APM_ENABLED:                       "true"
    DD_APM_NON_LOCAL_TRAFFIC:             "true"
    DD_LOGS_ENABLED:                      "true"
    DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL: "true"
    DD_PROCESS_AGENT_ENABLED:             "true"
    DD_DOGSTATSD_NON_LOCAL_TRAFFIC:       "true"
    DD_CONTAINER_EXCLUDE:                 "name:aviondash-dd-agent"
    DD_ENV:                               demo
    DD_SERVICE:                           aviondash
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /proc/:/host/proc/:ro
    - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
  ports:
    - "8125:8125/udp"
    - "8126:8126"
  networks:
    - backend
    - frontend
```

Also add `datadog-agent` to the `app` service's `depends_on` block if you want the app to wait for the agent.

### 1.3 Enable APM tracing in the app

In `docker-compose.yml`, set this environment variable on the `app` service:

```yaml
DD_TRACE_ENABLED: "true"
```

### 1.4 Restart everything

```bash
docker compose up -d
```

### 1.5 Verify the agent is running

```bash
docker compose exec datadog-agent agent status
```

Look for:
- `APM Agent running`
- `Logs Agent running` with `Status: Running`
- `Checks: docker (OK)`

---

## Step 2 — APM (Distributed Tracing)

The FastAPI app includes `ddtrace` in its requirements. When `DD_TRACE_ENABLED=true` and the agent is reachable, traces are sent automatically.

**Auto-instrumented libraries:**
- FastAPI (all request/response spans)
- SQLAlchemy (all query spans with SQL text)
- httpx (any outbound HTTP calls)

**Trace tags automatically applied:**
```
service: aviondash-app
env: demo
version: 1.0.0
```

### Generate initial traces

```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=aviondash123" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Hit several endpoints to populate the service map
for endpoint in /api/dashboard/summary /api/flights/ /api/aircraft/ /api/airports/; do
  curl -s -H "Authorization: Bearer $TOKEN" http://localhost$endpoint > /dev/null
done
```

**Where to look in Datadog:**
- **APM → Services → aviondash-app**: Request rate, error rate, latency P50/P95/P99
- **APM → Service Map**: Shows web → app → mysql topology
- **APM → Traces**: Individual distributed traces with flame graphs

---

## Step 3 — Log Management

### Automatic collection

The Agent collects logs from all three containers via the Docker socket (`DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL: true`). No additional configuration is needed.

**Log formats by tier:**

| Tier | Format | Key fields |
|------|--------|------------|
| Nginx | JSON (`json_combined`) | `time`, `method`, `uri`, `status`, `request_time`, `upstream_response_time` |
| FastAPI | Python structured text | `asctime`, `levelname`, `name`, `message` |
| MySQL | MySQL error log format | `time`, `thread`, `type`, `message` |

### Create Log Pipelines

In Datadog: **Logs → Pipelines → New Pipeline**

**Pipeline 1 — Nginx Access Logs**
- Filter: `source:nginx`
- Add Processors:
  1. **JSON Parser**: Parse the `message` field as JSON
  2. **Status Remapper**: Map `status` field → `http.status_code`
  3. **Duration Remapper**: Map `request_time` → `duration` (multiply by 1000 for ms)
  4. **Geo-IP Parser**: Map `remote_addr` → `network.client.geoip`

**Pipeline 2 — FastAPI Application Logs**
- Filter: `service:aviondash-app`
- Add Processors:
  1. **Parser** for structured log lines:
     ```
     %{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} \[%{DATA:logger}\] %{GREEDYDATA:message}
     ```
  2. **Status Remapper**: Map `level` → log status (INFO→info, WARNING→warn, ERROR→error)
  3. **Trace ID Remapper**: Link logs to APM traces via trace ID injection

### Useful Log Queries

```
# All application errors
service:aviondash-app status:error

# All active faults
service:aviondash-app "[FAULT]"

# Specific fault activity
service:aviondash-app "[FAULT][LOG_FLOOD]"

# Slow query injections
service:aviondash-app "[FAULT] slow_queries"

# Nginx 5xx errors
source:nginx @http.status_code:[500 TO 599]

# Failed logins
service:aviondash-app "Failed login"
```

---

## Step 4 — Infrastructure Metrics

With the agent running, these container metrics are collected automatically:

| Metric | Description |
|--------|-------------|
| `container.cpu.usage` | CPU % per container |
| `container.memory.usage` | Memory bytes per container |
| `container.net.bytes_sent` | Network TX per container |
| `container.net.bytes_rcvd` | Network RX per container |
| `container.io.read_bytes` | Disk read per container |
| `container.io.write_bytes` | Disk write per container |
| `container.running` | 1 if container up, 0 if down |
| `container.uptime` | Seconds since container started |
| `disk.in_use` | Disk usage fraction (0–1) |

**Filter by container:**
Use the tag `container_name:aviondash-app`, `container_name:aviondash-db`, or `container_name:aviondash-web`.

---

## Step 5 — Monitors

Create the following monitors in **Monitors → New Monitor**.

### Application Tier Monitors

---

**Monitor 1: High API Error Rate**
```
Type: Metric Alert
Query: sum(last_5m):sum:trace.fastapi.request.errors{service:aviondash-app}.as_rate() > 0.30
Alert threshold:   > 0.30  (30% error rate)
Warning threshold: > 0.10  (10% error rate)
Name: [AvionDash] High API Error Rate
Tags: service:aviondash-app, env:demo, tier:application
Message:
  🚨 AvionDash API error rate is {{value}}%.
  Fault likely active: high_error_rate or random_500s
  Check Chaos Control: http://localhost/#chaos
  View traces: https://app.datadoghq.com/apm/services/aviondash-app
```

---

**Monitor 2: P99 Latency Anomaly**
```
Type: Anomaly Alert
Query: anomalies(avg:trace.fastapi.request.duration{service:aviondash-app}, 'agile', 3)
Trigger: Anomalous for > 5 minutes
Name: [AvionDash] Latency Anomaly (P99)
Tags: service:aviondash-app, env:demo, tier:application
Message:
  ⚠️ AvionDash API latency is anomalous.
  Current: {{value}} | Expected: {{threshold}}
  Fault likely active: latency_spike or slow_queries
```

---

**Monitor 3: Slow Database Queries**
```
Type: Metric Alert
Query: avg(last_5m):avg:db.query.duration{service:aviondash-app} > 3000
Alert threshold:   > 3000 ms (3 seconds)
Warning threshold: > 1000 ms (1 second)
Name: [AvionDash] Slow Database Queries
Tags: service:aviondash-app, env:demo, tier:database
```

---

**Monitor 4: N+1 Query Detection**
```
Type: Change Alert
Query: change(sum(last_5m),last_1h):avg:db.query.count{service:aviondash-app}.as_rate() > 300
Name: [AvionDash] N+1 Query Pattern Detected
Tags: service:aviondash-app, env:demo, tier:database
Message:
  📊 Database query volume has increased significantly relative to request rate.
  Check APM traces for stacked DB spans — likely an N+1 query pattern.
```

---

**Monitor 5: Log Volume Anomaly**
```
Type: Log Alert
Query: logs("service:aviondash-app status:warn").rollup("count").last("5m") > 500
Name: [AvionDash] Log Flood Detected
Tags: service:aviondash-app, env:demo, tier:application
Message:
  📋 Warning log volume is abnormally high: {{value}} log lines in 5 minutes.
  Fault likely active: log_flood or cascading_failure
```

---

**Monitor 6: Login Failures**
```
Type: Log Alert
Query: logs("service:aviondash-app \"Failed login\"").rollup("count").last("5m") > 10
Name: [AvionDash] High Login Failure Rate
Tags: service:aviondash-app, env:demo, tier:application
```

---

### Container Tier Monitors

---

**Monitor 7: Container CPU Spike**
```
Type: Metric Alert
Query: avg(last_5m):avg:container.cpu.usage{container_name:aviondash-app} > 80
Alert threshold:   > 80%
Warning threshold: > 60%
Name: [AvionDash] Container CPU Spike
Tags: container_name:aviondash-app, env:demo, tier:container
Message:
  🔥 App container CPU usage is {{value}}%.
  Fault likely active: cpu_spike
```

---

**Monitor 8: Container Memory High**
```
Type: Metric Alert
Query: avg(last_5m):avg:container.memory.usage{container_name:aviondash-app} > 400000000
Alert threshold:   > 400 MB
Warning threshold: > 300 MB
Name: [AvionDash] Container Memory High
Tags: container_name:aviondash-app, env:demo, tier:container
```

---

**Monitor 9: Memory Leak Forecast**
```
Type: Forecast Alert
Query: forecast(max:container.memory.usage{container_name:aviondash-app}, 'linear', 1)
Threshold: > 500000000 (500 MB projected within 1 hour)
Name: [AvionDash] Memory Leak Forecast — OOM Risk
Tags: container_name:aviondash-app, env:demo, tier:container
Message:
  🔮 Memory is projected to exceed 500 MB within 1 hour.
  Fault likely active: memory_leak or container_oom_simulation
  Consider restarting: docker compose restart app
```

---

**Monitor 10: Container Restart Detected**
```
Type: Event Alert
Query: events("sources:docker tags:container_name:aviondash-app").rollup("count").last("5m") > 0
Name: [AvionDash] App Container Restarted
Tags: container_name:aviondash-app, env:demo, tier:container
Message:
  🔄 The aviondash-app container has restarted.
  This may be caused by: health_check_fail fault → Docker health check failing
  or an OOM-kill from: memory_leak / container_oom_simulation faults
```

---

**Monitor 11: App Container Down**
```
Type: Metric Alert
Query: avg(last_2m):avg:container.running{container_name:aviondash-app} < 1
Name: [AvionDash] App Container Not Running
Tags: container_name:aviondash-app, env:demo, tier:container
```

---

**Monitor 12: DB Container Down**
```
Type: Metric Alert
Query: avg(last_2m):avg:container.running{container_name:aviondash-db} < 1
Name: [AvionDash] DB Container Not Running
Tags: container_name:aviondash-db, env:demo, tier:database
```

---

**Monitor 13: Disk Usage High**
```
Type: Metric Alert
Query: max(last_5m):max:disk.in_use{host:aviondash-app} > 0.85
Alert threshold:   > 85%
Warning threshold: > 75%
Name: [AvionDash] Container Disk Fill
Tags: env:demo, tier:container
Message:
  💾 Container disk usage is at {{value}}%.
  Fault likely active: disk_fill
  The fill file will be removed when fault is disabled.
```

---

**Monitor 14: Nginx 5xx Rate**
```
Type: Log Alert
Query: logs("source:nginx @http.status_code:[500 TO 599]").rollup("count").last("5m") > 20
Name: [AvionDash] Nginx 5xx Error Rate
Tags: service:aviondash-web, env:demo, tier:web
```

---

### Composite Monitors

---

**Monitor 15: Cascading Failure — P1**
```
Type: Composite
Formula: monitor_1 AND monitor_2 AND monitor_5
  (High Error Rate AND Latency Anomaly AND Log Volume)
Name: [AvionDash] 🚨 CASCADING FAILURE — P1
Priority: 1 — Critical
Message:
  🚨 P1 INCIDENT — CASCADING FAILURE DETECTED

  Multiple AvionDash tiers are simultaneously degraded:
  • API error rate > 30%
  • Latency anomaly detected
  • Log volume spike

  Immediate actions:
  1. Check Chaos Control: http://localhost/#chaos
  2. View APM Service Map for propagation
  3. Correlate logs: service:aviondash-app "[FAULT]"
  4. Reset all faults: POST /api/chaos/reset-all
```

---

**Monitor 16: Container Resource Pressure**
```
Type: Composite
Formula: monitor_7 AND monitor_8
  (CPU Spike AND Memory High)
Name: [AvionDash] Container Resource Pressure
Priority: 2 — High
```

---

## Step 6 — Synthetic Tests

In Datadog: **Synthetics → New Test**

### Test 1: Login Flow (API Test — Multi-step)

```
Name: AvionDash — Login End-to-End
Type: API Test (multi-step)
Locations: AWS:us-east-1, AWS:eu-west-1
Schedule: Every 5 minutes

Steps:
  Step 1 — POST Login
    URL: http://YOUR_HOST/api/auth/token
    Method: POST
    Headers: Content-Type: application/x-www-form-urlencoded
    Body: username=demo&password=aviondash123
    Assertions:
      - Status code is 200
      - Body contains "access_token"
    Extracted variables:
      - TOKEN = jsonpath($.access_token)

  Step 2 — GET Dashboard
    URL: http://YOUR_HOST/api/dashboard/summary
    Method: GET
    Headers: Authorization: Bearer {{ TOKEN }}
    Assertions:
      - Status code is 200
      - Response time < 2000 ms
      - Body contains "flights"

  Step 3 — GET Flights
    URL: http://YOUR_HOST/api/flights/
    Method: GET
    Headers: Authorization: Bearer {{ TOKEN }}
    Assertions:
      - Status code is 200
      - Response time < 3000 ms
```

---

### Test 2: Health Check (API Test — Simple)

```
Name: AvionDash — Health Endpoint
Type: API Test
URL: http://YOUR_HOST/health
Method: GET
Assertions:
  - Status code is 200
  - Response time < 500 ms
  - Body contains "ok"
Schedule: Every 1 minute
Alert: After 2 consecutive failures
```

---

## Step 7 — SLOs

In Datadog: **SLOs → New SLO**

### SLO 1: API Availability

```
Type: Monitor-based SLO
Monitor: [AvionDash] High API Error Rate (Monitor 1)
Target: 99.5% over rolling 30 days
  → This allows 3.65 hours of downtime per month
Warning: 99.8% (1.46 hours/month)

Error Budget Burn Alerts:
  - Fast burn: 14.4x rate over 1h (consumes 2% of 30-day budget in 1h)
  - Slow burn: 6x rate over 6h  (consumes 5% of 30-day budget in 6h)
```

### SLO 2: API Latency

```
Type: Monitor-based SLO
Monitor: [AvionDash] P99 Latency Anomaly (Monitor 2)
Target: 95% of time within normal latency bounds
Rolling window: 7 days
```

---

## Step 8 — Dashboard

In Datadog: **Dashboards → New Dashboard** → "AvionDash Operations"

Suggested layout:

**Row 1 — Service Overview**
- Timeseries: `trace.fastapi.request.hits{service:aviondash-app}` — Request rate
- Timeseries: `trace.fastapi.request.errors{service:aviondash-app}` — Error rate
- Timeseries: `trace.fastapi.request.duration{service:aviondash-app}` by percentile
- Query Value: Active container count

**Row 2 — Container Resources**
- Timeseries: `container.cpu.usage` by `container_name`
- Timeseries: `container.memory.usage` by `container_name`
- Timeseries: `container.net.bytes_sent` + `container.net.bytes_rcvd`

**Row 3 — Database**
- Timeseries: `db.query.duration` by resource
- Timeseries: `db.query.count` by resource
- Query Value: DB error count (last 1h)

**Row 4 — Chaos State**
- Event timeline filtered by `[FAULT]`
- Log stream: `service:aviondash-app message:[FAULT]*`
- SLO status widget

---

## Tagging Reference

All resources use this consistent tag schema:

| Tag | Values | Used for |
|-----|--------|----------|
| `env` | `demo` | Environment grouping across all monitors |
| `service` | `aviondash-app`, `aviondash-web` | APM service identification |
| `version` | `1.0.0` | Deployment tracking |
| `tier` | `web`, `application`, `database`, `container` | Architecture layer |
| `container_name` | `aviondash-app`, `aviondash-db`, `aviondash-web` | Container-specific filtering |

These tags flow through automatically from the environment variables set in `docker-compose.yml` and the Docker labels on each service.

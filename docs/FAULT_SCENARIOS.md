# AvionDash Docker — Fault Scenarios

Complete reference for all 14 chaos fault injections available in the Chaos Control Centre. Each fault is designed to generate specific, observable Datadog signals suitable for demonstrating monitor types, APM features, and alerting capabilities.

---

## How the Chaos Engine Works

Faults are stored in a shared in-memory dictionary (`FAULT_STATE`) inside the FastAPI process. A middleware function inspects this state on every incoming request and applies the configured behaviour before the route handler runs. Container-tier faults additionally spawn background threads.

All fault activations are written to the application log with the `[FAULT]` prefix, making them easily filterable in Datadog Log Management.

### Enable via UI
Navigate to **Chaos Control** in the sidebar (admin role required). Toggle any fault card on or off.

### Enable via API
```bash
# Get token first
TOKEN=$(curl -s -X POST http://localhost/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=aviondash123" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Activate a fault
curl -X POST http://localhost/api/chaos/slow_queries/toggle \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Get current state of all faults
curl -H "Authorization: Bearer $TOKEN" http://localhost/api/chaos/status

# Reset everything
curl -X POST http://localhost/api/chaos/reset-all \
  -H "Authorization: Bearer $TOKEN"
```

---

## Application Tier Faults

These faults run inside the FastAPI process and affect application-layer behaviour.

---

### 1. Slow DB Queries
**Key:** `slow_queries` | **Severity:** WARNING

**What it does:** Injects a `time.sleep(random.uniform(3.0, 8.0))` before database operations on the `/api/flights/` endpoint. Every call to the flights list will block for 3–8 seconds before executing the actual SQL query.

**Datadog signals generated:**
- APM: `db.query.duration` rises dramatically in the trace flame graph
- APM: P95 and P99 latency for `GET /api/flights/` spikes
- APM: Slow spans appear in the service map between `aviondash-app` and `mysql`
- Logs: `[FAULT] slow_queries` warning logged on each affected request

**Monitor to demonstrate:**
```
Type: Metric Alert
Query: avg(last_5m):avg:trace.fastapi.request.duration{service:aviondash-app,resource_name:GET /api/flights/} > 3
Threshold: > 3 seconds average
```

**Recovery:** Disable the fault. Query times return to normal on the next request.

---

### 2. High Error Rate
**Key:** `high_error_rate` | **Severity:** CRITICAL

**What it does:** Returns HTTP 503 Service Unavailable on 60% of all non-health requests. Simulates a severely degraded upstream dependency or application crash loop.

**Datadog signals generated:**
- APM: `service.error.rate` climbs to ~60% — visible in the service map as red
- APM: Error count metric spikes across all resources
- Logs: `[FAULT] high_error_rate` error logged on each injected failure
- RUM (if configured): JS fetch errors increase dramatically
- SLO: Error budget burns rapidly

**Monitor to demonstrate:**
```
Type: Metric Alert
Query: sum(last_5m):sum:trace.fastapi.request.errors{service:aviondash-app}.as_rate() > 0.5
Threshold: > 50% error rate
```

**Demo note:** Combine with the cascading failure for maximum visual impact in the service map.

---

### 3. Random 500 Errors
**Key:** `random_500s` | **Severity:** WARNING

**What it does:** Returns HTTP 500 Internal Server Error on a random 35% of requests. Unlike `high_error_rate`, this is intermittent — harder to reproduce manually, more realistic of a flaky dependency.

**Datadog signals generated:**
- APM: Scattered error spans with no consistent resource pattern
- APM: Error rate rises but doesn't reach the `high_error_rate` monitor threshold — ideal for demonstrating SLO burn-rate alerts vs threshold alerts
- Logs: `[FAULT] random_500s` error logged

**Monitor to demonstrate:**
```
Type: SLO Alert (burn rate)
SLO Target: 99.5% availability
Alert: Error budget burn rate > 14.4x for last 1h
This triggers before a standard threshold monitor would fire.
```

---

### 4. Latency Spike
**Key:** `latency_spike` | **Severity:** WARNING

**What it does:** Adds `time.sleep(random.uniform(2.0, 6.0))` to every request, including the login endpoint. Every API call takes 2–6 seconds longer than normal.

**Datadog signals generated:**
- APM: P99 latency anomaly on all endpoints simultaneously
- APM: Apdex score drops — visible in the service overview
- APM: Trace duration histograms shift right
- Logs: `[FAULT] latency_spike Xs on /path` logged per request

**Monitor to demonstrate:**
```
Type: Anomaly Alert
Query: anomalies(avg:trace.fastapi.request.duration{service:aviondash-app}, 'agile', 3)
Evaluates: last 30 minutes
This demonstrates anomaly detection vs static thresholds.
```

**Demo note:** Enable alongside `slow_queries` to show correlated latency across the full request path vs just the DB layer.

---

### 5. Memory Leak
**Key:** `memory_leak` | **Severity:** CRITICAL

**What it does:** Allocates 512 KB of memory per request and appends it to `app.state.leak` without ever releasing it. Memory grows continuously proportional to request volume.

**Datadog signals generated:**
- `container.memory.usage` for `aviondash-app` climbs steadily and visibly
- Forecast monitor triggers well before the container hits its limit
- If a memory limit is set (e.g., `mem_limit: 512m` in compose), the container will eventually be OOM-killed and restart — generating a container restart event

**Monitor to demonstrate:**
```
Type: Forecast Alert
Query: forecast(max:container.memory.usage{container_name:aviondash-app}, 'linear', 1)
Threshold: > 400000000 (400 MB) within 1 hour
```

**Recovery:** Disable the fault. Memory already allocated will not be freed until the container restarts. To force release: `docker compose restart app`.

---

### 6. CPU Spike
**Key:** `cpu_spike` | **Severity:** WARNING

**What it does:** Executes a 300ms CPU-burning busy-wait loop (`while time.time() < deadline: _ = random.random() ** 0.5`) on every request. Under any meaningful load, the container CPU usage will saturate.

**Datadog signals generated:**
- `container.cpu.usage` for `aviondash-app` spikes significantly
- CPU throttling metrics increase if a CPU limit is configured
- Process agent shows the Python process at the top of CPU rankings
- Response times increase as the CPU cannot service requests quickly

**Monitor to demonstrate:**
```
Type: Metric Alert
Query: avg(last_5m):avg:container.cpu.usage{container_name:aviondash-app} > 80
Threshold: > 80% CPU utilisation
```

---

### 7. N+1 Query Pattern
**Key:** `n_plus_one` | **Severity:** WARNING

**What it does:** When fetching the flights list, issues one additional `SELECT COUNT(*) FROM flights WHERE origin_iata = ?` query for every row returned. A request returning 25 flights will generate 26 database queries instead of 1.

**Datadog signals generated:**
- APM flame graph shows dozens of small, stacked DB spans beneath the flights endpoint
- `db.query.count` metric spikes relative to request count (ratio becomes 26:1 instead of 1:1)
- Visible in APM Trace Analytics as a distinctive pattern: many identical short-duration DB spans

**Monitor to demonstrate:**
```
Type: Change Alert
Query: change(sum(last_5m),last_1h):avg:db.query.count{service:aviondash-app}.as_rate() > 400
Detects: sudden increase in query volume without corresponding traffic increase
```

**Demo value:** This is the most visually compelling fault in the APM trace view. The flame graph pattern is unmistakably recognisable as an ORM anti-pattern.

---

### 8. DB Connection Pool Exhaustion
**Key:** `db_pool_exhaustion` | **Severity:** CRITICAL

**What it does:** Holds each database connection open for 5–12 seconds per request via `time.sleep()`. The SQLAlchemy pool has 10 connections + 20 overflow = 30 total. Under concurrent load, all connections will be held and subsequent requests will queue or timeout.

**Datadog signals generated:**
- APM: Long-running spans on DB operations
- APM: Eventually `QueuePool limit of size 10 overflow 20 reached` errors when pool is exhausted
- Response times become highly variable — some requests fast, others extremely slow
- `db.pool.connections.waiting` metric increases (if DB monitoring enabled)

**Monitor to demonstrate:**
```
Type: Composite Monitor
Condition: (Latency P95 > 5s) AND (Error rate > 10%)
This demonstrates how pool exhaustion manifests differently from a simple latency issue.
```

---

### 9. Log Flood
**Key:** `log_flood` | **Severity:** WARNING

**What it does:** Emits 50 `WARNING`-level log lines per request to the application log. Under normal request rates, this generates hundreds of log lines per second.

**Datadog signals generated:**
- Log ingestion volume for `service:aviondash-app` increases by 50x
- Log volume anomaly monitor fires
- Log pipeline may experience backpressure
- Log-based metrics (if configured) spike dramatically

**Monitor to demonstrate:**
```
Type: Log Alert
Query: logs("service:aviondash-app status:warn [FAULT][LOG_FLOOD]").rollup("count").last("5m") > 500
```

**Demo value:** Excellent for demonstrating log volume anomaly detection and the cost implications of uncontrolled logging.

---

## Container / Infrastructure Tier Faults

These faults simulate failures at the Docker/container infrastructure layer rather than the application code.

---

### 10. Health Check Failure
**Key:** `health_check_fail` | **Severity:** CRITICAL

**What it does:** Returns HTTP 503 from the `/health` endpoint. Docker's built-in health check polls this endpoint and marks the container `unhealthy` after `retries` (3) consecutive failures. Docker Compose will then restart the container automatically.

**Datadog signals generated:**
- `container.health` metric transitions from healthy → unhealthy
- Datadog Synthetic test fires (if configured against `/health`)
- Container restart event generated — visible in the event stream
- The brief downtime during restart appears as a gap in APM data

**Monitor to demonstrate:**
```
Type: Service Check
Monitor: HTTP check on http://localhost/health
Alert: 3 consecutive failures
Warning: 1 failure
```

**Demo value:** Shows the full lifecycle of a container health failure, automatic recovery, and the observability gap during restart. Pairs well with a Synthetic monitor for real-time alerting.

**Note:** After enabling this fault, the container will restart in ~45 seconds (3 failed checks × 15s interval). This resets all in-memory fault state, so other active faults will also be cleared.

---

### 11. Container OOM Simulation
**Key:** `container_oom_simulation` | **Severity:** CRITICAL

**What it does:** Spawns a background thread that allocates 5 MB chunks every second, growing without bound. Unlike the `memory_leak` fault (which is request-proportional), this grows at a fixed rate regardless of traffic.

**Growth rate:** ~5 MB/second → ~300 MB/minute

**Datadog signals generated:**
- `container.memory.usage` climbs linearly at 5 MB/s — a clear ramp visible in dashboards
- Forecast monitor fires within minutes of activation
- Change monitor fires as the rate of change is dramatic
- If `mem_limit` is set in docker-compose, triggers actual OOM-kill and container restart

**Monitor to demonstrate:**
```
Type: Forecast Alert
Query: forecast(max:container.memory.usage{container_name:aviondash-app}, 'linear', 1)
Threshold: > 500000000 (500 MB) forecast within 30 minutes

Type: Change Alert
Query: change(avg(last_5m),last_30m):avg:container.memory.usage{container_name:aviondash-app} > 100000000
Detects: 100 MB increase over 30 minutes
```

**Recovery:** Disable the fault. Memory is released (via `gc.collect()`) and the background thread exits.

---

### 12. Network Partition (DB Unreachable)
**Key:** `network_partition` | **Severity:** CRITICAL

**What it does:** Calls `engine.dispose()` on the SQLAlchemy connection pool, immediately closing all active database connections. Simulates a network split between the `aviondash-app` container and the `aviondash-db` container. New DB connections will fail until the fault is disabled.

**Datadog signals generated:**
- All API endpoints that require the database return 500 errors immediately
- APM: `OperationalError: (2003) Can't connect to MySQL server` spans appear in the DB layer
- Error propagation is visible across the service map: web → app → db all turn red
- `/health/db` endpoint returns 503, triggering any health-check based monitors

**Monitor to demonstrate:**
```
Type: Composite Monitor
Condition: (DB health check FAILING) AND (API error rate > 80%)
This demonstrates how a database network issue propagates through every tier.
```

**Recovery:** Disable the fault. SQLAlchemy automatically re-establishes connections on the next request — no container restart needed.

---

### 13. Disk Fill
**Key:** `disk_fill` | **Severity:** WARNING

**What it does:** Spawns a background thread that writes 100 KB chunks to `/var/log/aviondash/disk_fill.log` every 200ms (~500 KB/second). If left running long enough, this will fill the container's log volume.

**Growth rate:** ~500 KB/second → ~30 MB/minute → ~1.8 GB/hour

**Datadog signals generated:**
- `disk.in_use` for the log volume mount climbs steadily
- Disk usage percentage alert fires as the threshold is crossed
- If disk fills completely: application log writes fail, generating additional errors
- Log volume anomaly for the disk_fill log file

**Monitor to demonstrate:**
```
Type: Metric Alert
Query: max(last_5m):max:disk.in_use{host:aviondash-app,device:/dev/sda} > 0.80
Threshold: > 80% disk usage
Warning: > 70%
```

**Recovery:** Disable the fault. The background thread stops and the fill file is deleted automatically.

---

### 14. Cascading Failure ⚡
**Key:** `cascading_failure` | **Severity:** CRITICAL

**What it does:** A meta-fault that simultaneously activates four faults:
1. `slow_queries` — database layer slows
2. `high_error_rate` — 60% of requests fail
3. `latency_spike` — all requests slow by 2–6 seconds
4. `log_flood` — log volume explodes

This models a realistic cascading outage where a slow database causes request queuing, which causes timeouts, which causes retries, which causes more load — the classic cascade pattern.

**Datadog signals generated:**
- All four individual fault signals fire simultaneously
- Composite monitor triggers (requires all four constituent monitors to be alerting)
- Service map shows every service in the red
- The correlation between metrics, traces, and logs is immediately visible
- APM error count, latency P99, DB query duration, and log volume all spike together

**Monitor to demonstrate:**
```
Type: Composite Monitor
Formula: error_rate_monitor AND latency_monitor AND log_volume_monitor AND db_latency_monitor
Priority: P1 — Critical
Message: 🚨 CASCADING FAILURE detected on AvionDash. All four signals firing simultaneously.
         Check Chaos Control: http://localhost/#chaos
         Correlate in APM Service Map and Logs.
```

**Demo script:**
1. Open Datadog APM Service Map
2. Open Log Explorer with `service:aviondash-app`
3. Open the Infrastructure Metrics for `aviondash-app`
4. Enable `cascading_failure` in Chaos Control
5. Walk through how each signal appears and correlates within 30 seconds
6. Show the composite monitor firing
7. Disable all faults with Reset All — show recovery in real time

---

## Recommended Demo Sequences

### Sequence A: APM Deep Dive (15 min)
1. Enable `n_plus_one` → show APM flame graph with stacked DB spans
2. Enable `slow_queries` → show DB span duration anomaly
3. Enable both simultaneously → show compound effect on P99
4. Reset all → show recovery

### Sequence B: Infrastructure Under Pressure (10 min)
1. Enable `container_oom_simulation` → show memory forecast
2. Enable `cpu_spike` → show CPU metrics alongside memory
3. Enable `disk_fill` → show disk growth
4. Reset all

### Sequence C: Full Outage Response (20 min)
1. Open: APM Service Map, Log Explorer, Infrastructure Metrics, Synthetic test
2. Enable `cascading_failure`
3. Walk through the Datadog incident timeline
4. Demonstrate log correlation with traces (trace IDs in logs)
5. Resolve: Reset All
6. Show recovery across all four signals

### Sequence D: SLO Burn Rate (ongoing)
1. Enable `random_500s` (intermittent, 35% error rate)
2. Navigate to SLOs in Datadog
3. Watch the error budget burn rate accelerate
4. Show how burn-rate alerts fire before the SLO target is breached

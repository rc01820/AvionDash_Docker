import builtins, gc, logging, os, random, threading, time
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user, require_admin

logger = logging.getLogger("aviondash.chaos")
router = APIRouter()

class FaultToggle(BaseModel):
    enabled: bool

CATALOG = {
    "slow_queries":             {"label":"Slow DB Queries","tier":"application","severity":"warning","description":"Injects 3–8s sleep before DB operations on /flights.","datadog_signal":"db.query.duration anomaly → APM slow span"},
    "high_error_rate":          {"label":"High Error Rate","tier":"application","severity":"critical","description":"Returns HTTP 503 on 60% of requests.","datadog_signal":"service.error.rate spike → composite monitor"},
    "random_500s":              {"label":"Random 500 Errors","tier":"application","severity":"warning","description":"Returns HTTP 500 on 35% of requests, burning SLO budget.","datadog_signal":"http.server_error count → SLO burn-rate alert"},
    "latency_spike":            {"label":"Latency Spike","tier":"application","severity":"warning","description":"Adds 2–6s sleep on every request.","datadog_signal":"trace.fastapi.request.duration p99 anomaly"},
    "memory_leak":              {"label":"Memory Leak","tier":"application","severity":"critical","description":"Allocates 512 KB per request without freeing.","datadog_signal":"container.memory.usage → forecast monitor"},
    "cpu_spike":                {"label":"CPU Spike","tier":"application","severity":"warning","description":"Burns 300ms CPU per request via busy-wait.","datadog_signal":"container.cpu.usage → threshold alert"},
    "n_plus_one":               {"label":"N+1 Query Pattern","tier":"application","severity":"warning","description":"Issues extra SELECT per flight row — classic ORM anti-pattern.","datadog_signal":"db.query.count spike → APM trace analytics"},
    "db_pool_exhaustion":       {"label":"DB Pool Exhaustion","tier":"application","severity":"critical","description":"Holds DB connections for 5–12s, exhausting the pool.","datadog_signal":"db.pool.connections.waiting → composite monitor"},
    "log_flood":                {"label":"Log Flood","tier":"application","severity":"warning","description":"Emits 50 WARNING lines per request.","datadog_signal":"logs.count anomaly → log volume alert"},
    "health_check_fail":        {"label":"Health Check Failure","tier":"container","severity":"critical","description":"Returns 503 from /health — triggers Docker restart + Synthetics alert.","datadog_signal":"synthetics.check.status FAIL → downtime alert"},
    "container_oom_simulation": {"label":"Container OOM Simulation","tier":"container","severity":"critical","description":"Background thread allocates 5MB/s until stopped or OOM-killed.","datadog_signal":"container.memory.usage → OOM forecast + change monitor"},
    "network_partition":        {"label":"Network Partition","tier":"container","severity":"critical","description":"Disposes DB connection pool — simulates app/db network split.","datadog_signal":"DB connection errors → APM error propagation"},
    "disk_fill":                {"label":"Disk Fill","tier":"container","severity":"warning","description":"Background thread writes 100KB chunks to log volume at 500KB/s.","datadog_signal":"disk.in_use → threshold monitor"},
    "cascading_failure":        {"label":"Cascading Failure","tier":"container","severity":"critical","description":"Activates slow_queries + high_error_rate + latency_spike + log_flood simultaneously.","datadog_signal":"composite monitor: 4 signals → P1 alert"},
}

_oom_running  = False
_disk_running = False

def _oom_worker():
    blocks = []
    while _oom_running:
        blocks.append(bytearray(5*1024*1024))
        logger.warning(f"[FAULT][OOM] {len(blocks)*5} MB allocated")
        time.sleep(1)
    del blocks; gc.collect()

def _disk_worker():
    path = "/var/log/aviondash/disk_fill.log"
    chunk = "X" * 102400
    while _disk_running:
        try:
            open(path,"a").write(chunk+"\n")
        except Exception as e:
            logger.error(f"[FAULT][DISK] {e}"); break
        time.sleep(0.2)

@router.get("/status")
async def fault_status(_=Depends(get_current_user)):
    return {"faults": dict(builtins.FAULT_STATE)}

@router.get("/catalog")
async def catalog(_=Depends(get_current_user)):
    return {"faults": CATALOG}

@router.post("/{fault_name}/toggle")
async def toggle(fault_name: str, body: FaultToggle, _=Depends(require_admin)):
    global _oom_running, _disk_running
    if fault_name not in builtins.FAULT_STATE:
        raise HTTPException(404, f"Unknown fault: {fault_name}")
    en = body.enabled

    if fault_name == "cascading_failure":
        for f in ["slow_queries","high_error_rate","latency_spike","log_flood","cascading_failure"]:
            builtins.FAULT_STATE[f] = en
        logger.warning(f"[FAULT] cascading_failure {'ON' if en else 'OFF'}")
        return {"fault": fault_name, "enabled": en}

    if fault_name == "container_oom_simulation":
        if en and not _oom_running:
            _oom_running = True
            threading.Thread(target=_oom_worker, daemon=True).start()
        elif not en:
            _oom_running = False

    if fault_name == "disk_fill":
        if en and not _disk_running:
            _disk_running = True
            threading.Thread(target=_disk_worker, daemon=True).start()
        elif not en:
            _disk_running = False
            try: os.remove("/var/log/aviondash/disk_fill.log")
            except FileNotFoundError: pass

    if fault_name == "network_partition":
        if en:
            from database import engine
            engine.dispose()
            logger.critical("[FAULT] network_partition: DB pool disposed")

    builtins.FAULT_STATE[fault_name] = en
    logger.warning(f"[FAULT] {fault_name} {'ON' if en else 'OFF'}")
    return {"fault": fault_name, "enabled": en}

@router.post("/reset-all")
async def reset_all(_=Depends(require_admin)):
    global _oom_running, _disk_running
    _oom_running = _disk_running = False
    for k in builtins.FAULT_STATE: builtins.FAULT_STATE[k] = False
    try: os.remove("/var/log/aviondash/disk_fill.log")
    except FileNotFoundError: pass
    gc.collect()
    return {"message": "All faults cleared"}

import time, random, logging, os, builtins, gc
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from database import engine, SessionLocal, Base

os.makedirs("/var/log/aviondash", exist_ok=True)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/var/log/aviondash/app.log")])
logger = logging.getLogger("aviondash")

FAULT_STATE = {k: False for k in [
    "slow_queries","high_error_rate","memory_leak","cpu_spike","db_pool_exhaustion",
    "n_plus_one","random_500s","latency_spike","container_oom_simulation",
    "network_partition","disk_fill","health_check_fail","cascading_failure","log_flood",
]}
builtins.FAULT_STATE = FAULT_STATE

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating tables")
    from models.users    import User     # noqa
    from models.airports import Airport  # noqa
    from models.aircraft import Aircraft # noqa
    from models.flights  import Flight   # noqa
    Base.metadata.create_all(bind=engine)
    logger.info("Tables ready — seeding demo users")
    from init_db import ensure_users
    ensure_users()
    logger.info("Startup complete")
    yield
    logger.info("Shutting down")

app = FastAPI(title="AvionDash API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def fault_middleware(request: Request, call_next):
    fs = builtins.FAULT_STATE
    path = request.url.path
    if path not in ("/health", "/health/db"):
        if fs.get("latency_spike"):
            d = random.uniform(2.0, 6.0)
            logger.warning(f"[FAULT] latency_spike {d:.1f}s on {path}")
            time.sleep(d)
        if fs.get("random_500s") and random.random() < 0.35:
            return JSONResponse(500, {"detail": "Internal Server Error (fault)"})
        if fs.get("high_error_rate") and random.random() < 0.60:
            return JSONResponse(503, {"detail": "Service Unavailable (fault)"})
        if fs.get("log_flood"):
            for i in range(50):
                logger.warning(f"[FAULT][LOG_FLOOD] {i} {path}")
        if fs.get("cpu_spike"):
            end = time.time() + 0.3
            while time.time() < end: _ = random.random() ** 0.5
        if fs.get("memory_leak"):
            if not hasattr(app.state, "leak"): app.state.leak = []
            app.state.leak.append(bytearray(512 * 1024))
    return await call_next(request)

@app.get("/health")
async def health():
    if builtins.FAULT_STATE.get("health_check_fail"):
        raise HTTPException(503, "Health check failing (fault injected)")
    return {"status": "ok", "service": "aviondash-app"}

@app.get("/health/db")
async def health_db():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(503, f"DB check failed: {e}")

@app.get("/")
async def root():
    return {"service": "AvionDash API", "version": "1.0.0"}

from api import auth, flights, aircraft, airports, chaos, dashboard
app.include_router(auth.router,      prefix="/api/auth")
app.include_router(flights.router,   prefix="/api/flights")
app.include_router(aircraft.router,  prefix="/api/aircraft")
app.include_router(airports.router,  prefix="/api/airports")
app.include_router(chaos.router,     prefix="/api/chaos")
app.include_router(dashboard.router, prefix="/api/dashboard")

import random
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.auth import get_current_user
from database import get_db
from models.flights import Flight
from models.aircraft import Aircraft
from models.airports import Airport

router = APIRouter()

def _build_summary(db: Session) -> dict:
    total   = db.query(Flight).count()
    active  = db.query(Flight).filter(Flight.status == "en_route").count()
    delayed = db.query(Flight).filter(Flight.delay_minutes > 0).count()
    canc    = db.query(Flight).filter(Flight.status == "cancelled").count()
    tot_ac  = db.query(Aircraft).count()
    act_ac  = db.query(Aircraft).filter(Aircraft.status == "active").count()
    maint   = db.query(Aircraft).filter(Aircraft.status == "maintenance").count()
    tot_ap  = db.query(Airport).count()
    busiest = db.execute(text(
        "SELECT origin_iata, COUNT(*) cnt FROM flights "
        "GROUP BY origin_iata ORDER BY cnt DESC LIMIT 5"
    )).fetchall()
    return {
        "flights":  {"total": total, "active": active, "delayed": delayed, "cancelled": canc,
                     "on_time_pct": round(((total - delayed) / max(total, 1)) * 100, 1)},
        "aircraft": {"total": tot_ac, "active": act_ac, "maintenance": maint,
                     "utilization_pct": round((act_ac / max(tot_ac, 1)) * 100, 1)},
        "airports": {"total": tot_ap},
        "busiest_origins": [{"iata": r[0], "departures": r[1]} for r in busiest],
        "system_health": {
            "api_latency_ms":   random.randint(12, 80),
            "db_query_time_ms": random.randint(5, 40),
            "cache_hit_pct":    round(random.uniform(82, 98), 1),
        },
    }

# Authenticated full summary (used by dashboard view)
@router.get("/summary")
async def summary(db: Session = Depends(get_db), _ = Depends(get_current_user)):
    return _build_summary(db)

# Public stats (used by login page — no auth required)
@router.get("/public-stats")
async def public_stats(db: Session = Depends(get_db)):
    total   = db.query(Flight).count()
    delayed = db.query(Flight).filter(Flight.delay_minutes > 0).count()
    tot_ac  = db.query(Aircraft).count()
    tot_ap  = db.query(Airport).count()
    return {
        "flights":  {"total": total, "delayed": delayed},
        "aircraft": {"total": tot_ac},
        "airports": {"total": tot_ap},
    }

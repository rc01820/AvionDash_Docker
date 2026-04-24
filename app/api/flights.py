import builtins, logging, random, time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.auth import get_current_user
from database import get_db
from models.flights import Flight

logger = logging.getLogger("aviondash.flights")
router = APIRouter()

class FlightOut(BaseModel):
    id: int; flight_number: str; origin_iata: str; destination_iata: str
    status: str; departure_time: Optional[str]; arrival_time: Optional[str]
    gate: Optional[str]; altitude_ft: Optional[int]; speed_kts: Optional[int]
    lat: Optional[float]; lon: Optional[float]; fuel_remaining_pct: Optional[float]
    delay_minutes: int; notes: Optional[str]
    class Config: from_attributes = True

def row_to_out(f: Flight) -> FlightOut:
    return FlightOut(
        id=f.id, flight_number=f.flight_number, origin_iata=f.origin_iata,
        destination_iata=f.destination_iata, status=f.status,
        departure_time=str(f.departure_time) if f.departure_time else None,
        arrival_time=str(f.arrival_time) if f.arrival_time else None,
        gate=f.gate, altitude_ft=f.altitude_ft, speed_kts=f.speed_kts,
        lat=f.lat, lon=f.lon, fuel_remaining_pct=f.fuel_remaining_pct,
        delay_minutes=f.delay_minutes or 0, notes=f.notes,
    )

@router.get("/", response_model=List[FlightOut])
async def list_flights(status: Optional[str]=Query(None), limit: int=Query(50,le=200),
                       db: Session=Depends(get_db), _=Depends(get_current_user)):
    fs = builtins.FAULT_STATE
    if fs.get("slow_queries"):
        delay = random.uniform(3.0, 8.0)
        logger.warning(f"[FAULT] slow_queries: {delay:.1f}s")
        time.sleep(delay)
    if fs.get("db_pool_exhaustion"):
        time.sleep(random.uniform(5.0, 12.0))
    q = db.query(Flight)
    if status: q = q.filter(Flight.status == status)
    if fs.get("n_plus_one"):
        rows = q.limit(limit).all()
        for f in rows:
            db.execute(text("SELECT COUNT(*) FROM flights WHERE origin_iata=:i"), {"i": f.origin_iata})
        return [row_to_out(f) for f in rows]
    return [row_to_out(f) for f in q.order_by(Flight.departure_time.desc()).limit(limit).all()]

@router.get("/stats")
async def stats(db: Session=Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("SELECT status, COUNT(*) FROM flights GROUP BY status")).fetchall()
    return {"total": db.query(Flight).count(),
            "by_status": {r[0]: r[1] for r in rows},
            "delayed": db.query(Flight).filter(Flight.delay_minutes > 0).count()}

@router.get("/{flight_id}", response_model=FlightOut)
async def get_flight(flight_id: int, db: Session=Depends(get_db), _=Depends(get_current_user)):
    f = db.query(Flight).filter(Flight.id == flight_id).first()
    if not f: raise HTTPException(404, "Flight not found")
    return row_to_out(f)

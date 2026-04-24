from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.auth import get_current_user
from database import get_db
from models.aircraft import Aircraft

router = APIRouter()

class AircraftOut(BaseModel):
    id: int; tail_number: str; model: str; manufacturer: str
    capacity: int; range_nm: int; status: str; engine_type: Optional[str]
    year_manufactured: Optional[int]; flight_hours: float
    class Config: from_attributes = True

@router.get("/", response_model=List[AircraftOut])
async def list_aircraft(status: Optional[str]=Query(None),
                        db: Session=Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Aircraft)
    if status: q = q.filter(Aircraft.status == status)
    return q.order_by(Aircraft.tail_number).all()

@router.get("/stats")
async def stats(db: Session=Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("SELECT status, COUNT(*) FROM aircraft GROUP BY status")).fetchall()
    return {"total": db.query(Aircraft).count(), "by_status": {r[0]: r[1] for r in rows}}

@router.get("/{aircraft_id}", response_model=AircraftOut)
async def get_aircraft(aircraft_id: int, db: Session=Depends(get_db), _=Depends(get_current_user)):
    a = db.query(Aircraft).filter(Aircraft.id == aircraft_id).first()
    if not a: raise HTTPException(404, "Aircraft not found")
    return a

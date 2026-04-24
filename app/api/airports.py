from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from api.auth import get_current_user
from database import get_db
from models.airports import Airport

router = APIRouter()

class AirportOut(BaseModel):
    id: int; iata_code: str; icao_code: Optional[str]; name: str
    city: str; country: str; lat: float; lon: float
    timezone: Optional[str]; elevation_ft: Optional[int]; runways: int
    class Config: from_attributes = True

@router.get("/", response_model=List[AirportOut])
async def list_airports(country: Optional[str]=Query(None),
                        db: Session=Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Airport)
    if country: q = q.filter(Airport.country == country)
    return q.order_by(Airport.iata_code).all()

@router.get("/{iata}", response_model=AirportOut)
async def get_airport(iata: str, db: Session=Depends(get_db), _=Depends(get_current_user)):
    a = db.query(Airport).filter(Airport.iata_code == iata.upper()).first()
    if not a: raise HTTPException(404, "Airport not found")
    return a

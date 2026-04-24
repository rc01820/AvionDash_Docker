from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from database import Base

class Airport(Base):
    __tablename__ = "airports"
    id           = Column(Integer, primary_key=True, index=True)
    iata_code    = Column(String(4), unique=True, nullable=False, index=True)
    icao_code    = Column(String(5), nullable=True)
    name         = Column(String(100), nullable=False)
    city         = Column(String(60), nullable=False)
    country      = Column(String(60), nullable=False)
    lat          = Column(Float, nullable=False)
    lon          = Column(Float, nullable=False)
    timezone     = Column(String(40), nullable=True)
    elevation_ft = Column(Integer, nullable=True)
    runways      = Column(Integer, default=2)
    created_at   = Column(DateTime, server_default=func.now())

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base

class Flight(Base):
    __tablename__ = "flights"
    id                 = Column(Integer, primary_key=True, index=True)
    flight_number      = Column(String(10), nullable=False, index=True)
    origin_iata        = Column(String(4), nullable=False)
    destination_iata   = Column(String(4), nullable=False)
    aircraft_id        = Column(Integer, nullable=True)
    status             = Column(Enum("scheduled","boarding","departed","en_route","landed","cancelled","diverted","delayed"), default="scheduled", nullable=False)
    departure_time     = Column(DateTime, nullable=False)
    arrival_time       = Column(DateTime, nullable=True)
    gate               = Column(String(5), nullable=True)
    altitude_ft        = Column(Integer, nullable=True)
    speed_kts          = Column(Integer, nullable=True)
    lat                = Column(Float, nullable=True)
    lon                = Column(Float, nullable=True)
    fuel_remaining_pct = Column(Float, nullable=True)
    delay_minutes      = Column(Integer, default=0)
    notes              = Column(Text, nullable=True)
    created_at         = Column(DateTime, server_default=func.now())
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now())

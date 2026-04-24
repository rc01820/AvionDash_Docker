from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func
from database import Base

class Aircraft(Base):
    __tablename__ = "aircraft"
    id                = Column(Integer, primary_key=True, index=True)
    tail_number       = Column(String(10), unique=True, nullable=False, index=True)
    model             = Column(String(50), nullable=False)
    manufacturer      = Column(String(50), nullable=False)
    capacity          = Column(Integer, nullable=False)
    range_nm          = Column(Integer, nullable=False)
    status            = Column(Enum("active","maintenance","grounded","retired"), default="active", nullable=False)
    engine_type       = Column(String(30), nullable=True)
    year_manufactured = Column(Integer, nullable=True)
    last_maintenance  = Column(DateTime, nullable=True)
    next_maintenance  = Column(DateTime, nullable=True)
    flight_hours      = Column(Float, default=0.0)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())

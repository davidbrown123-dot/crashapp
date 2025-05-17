# backend/app/models.py
from sqlalchemy import Column, Integer, String, DateTime
from .database import Base
import datetime

class Crash(Base):
    __tablename__ = "crashes"

    id = Column(Integer, primary_key=True, index=True)
    detection_timestamp = Column(DateTime, index=True) # Store as DateTime object
    video_filename = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
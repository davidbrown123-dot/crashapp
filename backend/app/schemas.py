# backend/app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Crash Schemas ---
class CrashBase(BaseModel):
    video_filename: str

class CrashCreate(CrashBase):
    # Timestamp will be added by the server based on AI script or server time
    detection_timestamp: datetime # Expecting ISO format string, Pydantic handles conversion

class Crash(CrashBase):
    id: int
    detection_timestamp: datetime
    created_at: datetime

    class Config:
        orm_mode = True # Allows creating schema from ORM model

# --- Weather Schemas ---
class WeatherData(BaseModel):
    weather_desc: str
    visibility_km: Optional[float] = None # Visibility might not always be available
    chance_of_rain: Optional[int] = None # Example field, adjust based on API
    is_raining: bool
    safe_speed_kmh: int
    location_used: str # To tell user if default or their location was used
# backend/app/crud.py
from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

def create_crash_record(db: Session, crash: schemas.CrashCreate):
    """Creates a new crash record in the database."""
    db_crash = models.Crash(
        detection_timestamp=crash.detection_timestamp,
        video_filename=crash.video_filename
        # created_at is handled by default in the model
    )
    db.add(db_crash)
    db.commit()
    db.refresh(db_crash)
    return db_crash

def get_crash_history(db: Session, skip: int = 0, limit: int = 100):
    """Retrieves a list of crash records from the database."""
    return db.query(models.Crash).order_by(models.Crash.detection_timestamp.desc()).offset(skip).limit(limit).all()
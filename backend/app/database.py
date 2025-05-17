# backend/app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Read the database URL from an environment variable
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    # Fallback for local development if DATABASE_URL isn't set
    # print("WARNING: DATABASE_URL not set, falling back to local SQLite.")
    # SQLALCHEMY_DATABASE_URL = "sqlite:///./crash_data.db" # Your old SQLite
    # For Render, it's better to ensure DATABASE_URL is always set.
    raise ValueError("DATABASE_URL environment variable not set!")


engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
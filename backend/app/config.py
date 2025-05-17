# backend/app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file in the 'backend' directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Points to backend/.env
load_dotenv(dotenv_path=dotenv_path)

WEATHERSTACK_API_KEY = os.getenv("WEATHERSTACK_API_KEY", "YOUR_WEATHERSTACK_API_KEY_HERE") # Get from environment or use placeholder

# Southfield, MI coordinates (approximate)
DEFAULT_LATITUDE = 42.4734
DEFAULT_LONGITUDE = -83.2219
DEFAULT_LOCATION_NAME = "Southfield, MI"

# Safe Speed Rules
BASE_SPEED_KMH = 120
RAIN_SPEED_REDUCTION_PERCENT = 25
VISIBILITY_REDUCTION_MEDIUM_PERCENT = 10 # 4-5km
VISIBILITY_REDUCTION_LOW_PERCENT = 20   # <4km
VISIBILITY_THRESHOLD_MEDIUM_KM = 5
VISIBILITY_THRESHOLD_LOW_KM = 4

# Make sure the API key placeholder is obvious if not set in .env
if WEATHERSTACK_API_KEY == "YOUR_WEATHERSTACK_API_KEY_HERE":
    print("WARNING: WEATHERSTACK_API_KEY not found in environment variables. Using placeholder.")
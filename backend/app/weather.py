# backend/app/weather.py
import requests
import logging
from . import config, schemas
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def get_weather_data(lat: float, lon: float) -> Optional[dict]:
    """Fetches weather data from Weatherstack API."""
    if not config.WEATHERSTACK_API_KEY or config.WEATHERSTACK_API_KEY == "YOUR_WEATHERSTACK_API_KEY_HERE":
        logger.error("Weatherstack API Key is not configured.")
        return None

    # Weatherstack API endpoint (use HTTPS)
    # Note: Free tier might only support HTTP, check their docs. Adjust if needed.
    # The 'current' endpoint is typical.
    api_url = f"http://api.weatherstack.com/current" # Use http if required by free plan

    params = {
        'access_key': config.WEATHERSTACK_API_KEY,
        'query': f"{lat},{lon}",
        'units': 'm' # Metric units (temp Celsius, speed km/h, visibility km)
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        # Basic check for error in response structure (Weatherstack specific)
        if 'error' in data:
            logger.error(f"Weatherstack API error: {data['error'].get('info', 'Unknown error')}")
            return None
        if 'current' not in data:
            logger.error(f"Unexpected Weatherstack API response format: {data}")
            return None

        logger.info(f"Weatherstack response: {data}") # Log the full response for debugging
        return data['current'] # Return the 'current' weather conditions object

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather data from Weatherstack: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during weather fetch: {e}")
        return None


def calculate_safe_speed(weather_conditions: dict) -> Tuple[schemas.WeatherData, bool]:
    """
    Calculates safe speed based on weather conditions using rules from config.
    Returns a tuple: (WeatherData schema object, success_flag)
    """
    base_speed = config.BASE_SPEED_KMH
    safe_speed = base_speed
    is_raining = False
    visibility_km = None
    chance_of_rain = None # Placeholder - Weatherstack free might not provide this directly
    weather_desc = "Unknown"

    if not weather_conditions:
        logger.warning("Cannot calculate safe speed, no weather conditions provided.")
        # Return default/unknown state but indicate failure
        return schemas.WeatherData(
            weather_desc="Weather data unavailable",
            visibility_km=None,
            chance_of_rain=None,
            is_raining=False,
            safe_speed_kmh=base_speed, # Default to base speed if weather unknown
            location_used="N/A" # Indicate failure
        ), False

    try:
        # Extract relevant info (adjust keys based on actual Weatherstack response!)
        visibility_km = weather_conditions.get('visibility') # Assuming API returns km directly with units=m
        precip_mm = weather_conditions.get('precip', 0) # Precipitation amount
        weather_code = weather_conditions.get('weather_code') # Weather code if available
        weather_descriptions = weather_conditions.get('weather_descriptions', ["Unknown"])
        weather_desc = ", ".join(weather_descriptions)

        # Determine if it's raining (simple check based on precip or description)
        # Weatherstack codes: https://weatherstack.com/documentation#weather_codes
        # Codes indicating rain: e.g., 176 (patchy rain), 263/266 (patchy light drizzle/drizzle),
        # 293-314 (moderate to heavy rain), 353-359 (showers) etc.
        rain_codes = [176, 263, 266, 293, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359]
        # A simpler check might be if 'rain' or 'drizzle' is in the description (case-insensitive)
        if any(term in desc.lower() for desc in weather_descriptions for term in ['rain', 'drizzle', 'shower']) or precip_mm > 0.1:
             is_raining = True
        # Alternatively, use weather_code if reliable:
        # if weather_code in rain_codes:
        #     is_raining = True

        # --- Apply Speed Reductions ---
        speed_reduction_percent = 0

        # 1. Rain Reduction (Highest priority if both conditions met)
        if is_raining:
            speed_reduction_percent = max(speed_reduction_percent, config.RAIN_SPEED_REDUCTION_PERCENT)

        # 2. Visibility Reduction (Check if visibility data is valid)
        if visibility_km is not None:
             if visibility_km < config.VISIBILITY_THRESHOLD_LOW_KM:
                 speed_reduction_percent = max(speed_reduction_percent, config.VISIBILITY_REDUCTION_LOW_PERCENT)
             elif visibility_km < config.VISIBILITY_THRESHOLD_MEDIUM_KM:
                 speed_reduction_percent = max(speed_reduction_percent, config.VISIBILITY_REDUCTION_MEDIUM_PERCENT)

        # Calculate final speed
        safe_speed = int(base_speed * (1 - speed_reduction_percent / 100))

        # Prepare response data
        weather_data = schemas.WeatherData(
            weather_desc=weather_desc,
            visibility_km=visibility_km,
            chance_of_rain=chance_of_rain, # Assign if available from API
            is_raining=is_raining,
            safe_speed_kmh=safe_speed,
            location_used="" # Will be set in the API endpoint
        )
        return weather_data, True

    except Exception as e:
        logger.error(f"Error processing weather conditions or calculating speed: {e}")
        # Return default/unknown state but indicate failure
        return schemas.WeatherData(
            weather_desc="Error processing weather",
            visibility_km=None,
            chance_of_rain=None,
            is_raining=False,
            safe_speed_kmh=base_speed,
            location_used="N/A"
        ), False


async def get_processed_weather(lat: Optional[float] = None, lon: Optional[float] = None) -> schemas.WeatherData:
    """
    Main function called by the API endpoint.
    Gets coords, fetches weather, calculates speed, returns final WeatherData.
    """
    location_used_name = ""
    if lat is None or lon is None:
        logger.info("Latitude/Longitude not provided, using default location.")
        lat = config.DEFAULT_LATITUDE
        lon = config.DEFAULT_LONGITUDE
        location_used_name = config.DEFAULT_LOCATION_NAME
    else:
        logger.info(f"Using provided coordinates: Lat={lat}, Lon={lon}")
        location_used_name = f"Provided Location ({lat:.2f}, {lon:.2f})" # Use provided coords

    raw_weather = get_weather_data(lat, lon)

    if raw_weather:
        weather_data, success = calculate_safe_speed(raw_weather)
        if success:
             weather_data.location_used = location_used_name
             return weather_data
        else:
            # Calculation failed, return the error state from calculate_safe_speed
            weather_data.location_used = location_used_name # Still indicate location attempted
            return weather_data
    else:
        # API call failed, return an error state
        logger.warning("Failed to retrieve weather data from API.")
        return schemas.WeatherData(
            weather_desc="Could not retrieve weather data",
            visibility_km=None,
            chance_of_rain=None,
            is_raining=False,
            safe_speed_kmh=config.BASE_SPEED_KMH, # Default to base
            location_used=location_used_name # Indicate location attempted
        )
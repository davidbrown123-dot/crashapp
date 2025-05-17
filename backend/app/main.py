# backend/app/main.py
import logging
import asyncio
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List

# FastAPI and related imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# SQLAlchemy and database imports
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base

# Application specific imports
from . import crud, models, schemas, weather, video_stream_buffer
from .websocket_manager import ConnectionManager

# --- Initial Setup ---
APP_DIR = Path(__file__).parent
try:
    # Ensure models are loaded before calling create_all if Base is from .database
    # If Base is imported from models, this is fine.
    models.Base.metadata.create_all(bind=engine)
    logging.info("DB tables checked/created.")
except Exception as e:
    logging.error(f"Error creating DB tables: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = FastAPI(title="Crash Notification System")

# --- CORS ---
origins = ["*", "null"] # Allow all origins and file:// for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Manager & DB Dependency ---
manager = ConnectionManager()
def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Placeholder Image Loading ---
placeholder_img_bytes: bytes | None = None
try:
    backend_dir = APP_DIR.parent # Assumes 'app' is inside 'backend'
    frontend_dir = backend_dir.parent / 'frontend' # Assumes 'frontend' is sibling of 'backend'

    # List of potential placeholder image paths to try
    possible_paths = [
        backend_dir / 'placeholder.jpg',
        backend_dir / 'loading.png',
        backend_dir / 'image.png',
        frontend_dir / 'icons' / 'icon-192x192.png' # Relative path from backend dir
    ]

    loaded_path = None
    for path in possible_paths:
        if path.is_file(): # Check if the file actually exists
            try:
                img = cv2.imread(str(path)) # Load image using OpenCV
                if img is not None:
                    logger.info(f"Loading placeholder image from: {path}")
                    # Resize to a standard size (e.g., 640x480)
                    img_resized = cv2.resize(img, (640, 480))
                    # Encode the resized image as JPEG
                    result, encoded_img = cv2.imencode('.jpg', img_resized)
                    if result:
                        placeholder_img_bytes = encoded_img.tobytes()
                        logger.info("Placeholder image loaded and encoded.")
                        loaded_path = path
                        break # Stop searching once a valid image is loaded and encoded
                    else:
                        logger.error(f"Failed to encode placeholder image from {path}.")
                # else: logger.warning(f"cv2.imread returned None for path: {path}") # May indicate invalid image format
            except Exception as read_err:
                 logger.error(f"Error reading image file {path}: {read_err}")
        # else: logger.debug(f"Placeholder path not found: {path}") # Can be noisy

    # If no image file was loaded successfully, create a black fallback
    if placeholder_img_bytes is None:
        logger.warning("No valid placeholder image file found. Creating black fallback (640x480).")
        try:
            black_img = np.zeros((480, 640, 3), dtype=np.uint8) # Create black image
            result, encoded_img = cv2.imencode('.jpg', black_img) # Encode as JPEG
            if result:
                placeholder_img_bytes = encoded_img.tobytes()
            else:
                logger.error("Failed to create or encode black placeholder image.")
                placeholder_img_bytes = b'' # Empty bytes as final fallback
        except Exception as np_err:
             logger.error(f"Error creating NumPy fallback image: {np_err}")
             placeholder_img_bytes = b''

except Exception as e:
    logger.error(f"General error during placeholder image setup: {e}")
    placeholder_img_bytes = b'' # Ensure defined as empty bytes on any error

# --- API Endpoints ---
@app.get("/", summary="Root endpoint", include_in_schema=False)
async def read_root():
    """Simple root endpoint (can redirect or serve main page)."""
    # Redirecting to /webapp by default (requires /webapp route below)
    logger.info("Redirecting / to /webapp")
    html_path = Path(__file__).parent.parent.parent / 'frontend' / 'webapp.html'
    if html_path.is_file():
        return FileResponse(html_path)
    else:
        return {"message": "Crash Notification Backend is running. webapp.html not found for root."}


@app.post("/api/crashes", response_model=schemas.Crash, status_code=status.HTTP_201_CREATED)
async def report_crash(crash_data: schemas.CrashCreate, db: Session = Depends(get_db)):
    """Handles crash reports from the AI script."""
    logger.info(f"Received crash report for video: {crash_data.video_filename}")
    try:
        db_crash = crud.create_crash_record(db=db, crash=crash_data)
        broadcast_data = {
            "id": db_crash.id,
            "detection_timestamp": db_crash.detection_timestamp.isoformat(),
            "video_filename": db_crash.video_filename,
            "created_at": db_crash.created_at.isoformat()
        }
        await manager.broadcast_crash_notification(broadcast_data)
        logger.info(f"Crash {db_crash.id} broadcasted.")
        return db_crash
    except Exception as e:
        logger.error(f"Error processing crash report: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error processing crash report")

@app.get("/api/crashes/history", response_model=List[schemas.Crash])
def get_crash_history_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Provides historical crash data."""
    logger.info(f"Fetching crash history (skip={skip}, limit={limit})")
    try:
        return crud.get_crash_history(db=db, skip=skip, limit=limit)
    except Exception as e:
        logger.error(f"Error fetching crash history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error fetching crash history")

@app.get("/api/weather_conditions", response_model=schemas.WeatherData)
async def get_weather_and_speed_endpoint(lat: Optional[float] = None, lon: Optional[float] = None):
    """Provides weather data and calculated safe speed."""
    logger.info(f"Request for weather conditions received. Lat: {lat}, Lon: {lon}")
    try:
        return await weather.get_processed_weather(lat, lon)
    except Exception as e:
        logger.error(f"Error getting processed weather: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error fetching weather data")

# --- Video Stream Endpoints ---
@app.post("/api/stream/push_frame", status_code=status.HTTP_204_NO_CONTENT)
async def push_video_frame(frame: bytes = Body(...)):
    """Receives JPEG frames from the AI script."""
    if not frame: raise HTTPException(status_code=400, detail="No frame data received")
    await video_stream_buffer.update_frame_global(frame)
    return None

@app.post("/api/stream/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_video_stream():
    """Clears the frame buffer when AI analysis stops."""
    logger.info("Received request to clear video stream buffer.")
    await video_stream_buffer.clear_frame_global()
    return None

# Define the boundary globally or pass it if preferred
mjpeg_boundary = "frame"

async def generate_mjpeg_stream():
    """Generator function that yields MJPEG stream parts."""
    while True:
        frame_bytes = await video_stream_buffer.get_latest_frame_global()
        if frame_bytes is None:
            if placeholder_img_bytes:
                frame_bytes = placeholder_img_bytes # Use placeholder if no live frame
            else:
                await asyncio.sleep(0.1) # Wait briefly if no frame and no placeholder
                continue
        try:
            # Format and yield the MJPEG frame part
            yield (
                b'--' + mjpeg_boundary.encode() + b'\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n'
                + frame_bytes + b'\r\n'
            )
            # Control stream frame rate
            await asyncio.sleep(0.05) # Approx 20 FPS
        except asyncio.CancelledError:
            # This happens naturally when the client disconnects
            logger.info("MJPEG stream connection closed/cancelled by client.")
            break
        except Exception as e:
            # Log other errors that might occur in the loop
            logger.error(f"Error in MJPEG stream loop: {e}")
            await asyncio.sleep(0.5) # Wait a bit longer after an error

@app.get("/stream/live", summary="Get live MJPEG video stream")
async def get_live_stream(request: Request):
    """Serves the MJPEG video stream to clients."""
    logger.info(f"Client {request.client.host}:{request.client.port} connected to MJPEG stream.")
    return StreamingResponse(
        generate_mjpeg_stream(), # Pass the generator
        media_type=f'multipart/x-mixed-replace; boundary={mjpeg_boundary}' # Set correct MIME type
    )

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for real-time alerts."""
    await manager.connect(websocket)
    try:
        while True:
            # Primarily keep connection open, can add message handling later if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WS Client disconnected: {websocket.client}")
    except Exception as e:
        # Handle unexpected errors during WebSocket connection
        logger.error(f"Error in WS connection for {websocket.client}: {e}")
        manager.disconnect(websocket) # Ensure cleanup

# --- Serve Frontend Static Files & HTML ---
# Define path relative to this file's location (app directory)
# Assumes 'frontend' is a sibling directory to 'backend'
frontend_dir_path = Path(__file__).parent.parent.parent / 'frontend'

try:
    # Mount the entire frontend directory to be served under /static
    # This makes CSS, JS, images, manifest, service worker available via /static/...
    app.mount("/static", StaticFiles(directory=frontend_dir_path), name="static_frontend")
    logger.info(f"Mounted static files from {frontend_dir_path} at /static")

    @app.get("/dashboard", response_class=FileResponse, include_in_schema=False)
    async def serve_dashboard_html():
         html_path = frontend_dir_path / 'dashboard.html'
         if html_path.is_file():
            return FileResponse(html_path)
         else:
            raise HTTPException(status_code=404, detail="dashboard.html not found")
    logger.info("Route /dashboard added to serve dashboard.html")

    # --- MODIFIED root route to serve index.html ---
    # Serve index.html (previously webapp.html) as the default root page "/"
    @app.get("/", response_class=FileResponse, include_in_schema=False)
    async def serve_root_index(): # Renamed function for clarity
         logger.info("Serving / as index.html") # Updated log message
         html_path = frontend_dir_path / 'index.html' # <<<--- CHANGED FILENAME HERE
         if html_path.is_file():
             return FileResponse(html_path)
         else:
             # Log the path being checked for easier debugging
             logger.error(f"index.html not found at expected path: {html_path}")
             raise HTTPException(status_code=404, detail="index.html not found for root")

except Exception as e:
     logger.error(f"Error setting up frontend static file/route serving: {e}")
     logger.error(f"Check that the 'frontend' directory exists at: {frontend_dir_path}")

# Note: Uvicorn command line arguments like --host, --port, --reload
# are used when running, not defined within the app itself.
# crash_notifier/ai_detector/ai_script.py

import cv2
from pathlib import Path
import time
import requests
from ultralytics import YOLO
import os
from datetime import datetime
import logging
import numpy as np # Might be needed for detections array manipulation

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
BASE_CAPTURE_PATH = Path("C:\Users\Abderrahmen\Desktop\captures\cars")
INPUT_DIR = BASE_CAPTURE_PATH
CRASH_DIR = BASE_CAPTURE_PATH / "Crashes"

# Backend Server URLs
BACKEND_BASE_URL = "http://127.0.0.1:8000" # Adjust if needed
CRASH_API_URL = f"{BACKEND_BASE_URL}/api/crashes"
FRAME_PUSH_URL = f"{BACKEND_BASE_URL}/api/stream/push_frame"
STREAM_CLEAR_URL = f"{BACKEND_BASE_URL}/api/stream/clear"

# Load YOLO model
MODEL_PATH = Path(__file__).parent / "best.pt"
if not MODEL_PATH.exists():
    logger.error(f"Model file not found at {MODEL_PATH}. Trying 'best.pt'.")
    MODEL_PATH = Path("best.pt")

try:
    model = YOLO(MODEL_PATH)
    # Get class names from the model if available (IMPORTANT for labels)
    class_names = model.names if hasattr(model, 'names') and model.names else {0: 'crash'} # Provide default
    logger.info(f"Successfully loaded YOLO model from {MODEL_PATH}")
    logger.info(f"Model class names: {class_names}")
except Exception as e:
    logger.error(f"Failed to load YOLO model from {MODEL_PATH}: {e}")
    exit()

# --- Backend Communication --- (Functions remain the same)

def send_crash_notification_to_backend(video_filename):
    timestamp = datetime.now().isoformat()
    payload = {"detection_timestamp": timestamp, "video_filename": video_filename}
    try:
        response = requests.post(CRASH_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Sent notification for {video_filename}. Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e: logger.error(f"⚠️ Backend notification failed: {e}"); return False
    except Exception as e: logger.error(f"⚠️ Unexpected error during notification: {str(e)}"); return False

def push_frame_to_backend(frame_jpeg_bytes):
    if not frame_jpeg_bytes: return False
    try:
        response = requests.post(FRAME_PUSH_URL, data=frame_jpeg_bytes, headers={'Content-Type': 'image/jpeg'}, timeout=0.5)
        response.raise_for_status(); return True
    except requests.exceptions.Timeout: return False
    except requests.exceptions.RequestException: return False
    except Exception as e: logger.error(f"⚠️ Frame push error: {str(e)}"); return False

def clear_backend_stream_buffer():
    try:
        response = requests.post(STREAM_CLEAR_URL, timeout=2)
        response.raise_for_status(); logger.info("Requested backend clear stream buffer.")
        return True
    except requests.exceptions.RequestException as e: logger.warning(f"⚠️ Failed clear stream buffer request: {e}"); return False
    except Exception as e: logger.error(f"⚠️ Error clearing stream buffer: {str(e)}"); return False

# --- Video Analysis with Bounding Box Drawing for Stream ---
def analyze_video(video_path):
    """
    Analyze video frames, draw detections, push frames with boxes to backend stream,
    and return True if a crash is detected.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Could not open video file: {video_path}")
        return None

    crash_detected_in_video = False
    frame_skip_yolo = 1  # Process every frame with YOLO to ensure boxes are up-to-date for drawing
    frame_skip_push = 1  # Push every frame to the stream
    frame_count = 0
    yolo_processed_count = 0
    frames_pushed_count = 0
    jpeg_quality = 75
    latest_detections = [] # Store detections from the last YOLO run

    logger.info(f"Starting analysis and streaming with boxes for: {video_path.name}")
    overall_start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.debug(f"End of video {video_path.name} reached.")
                break

            frame_count += 1
            display_frame = frame.copy() # Create a copy for drawing

            # --- YOLO Crash Detection ---
            # Run inference more frequently if possible to keep boxes current for drawing
            if frame_count % frame_skip_yolo == 0:
                yolo_processed_count += 1
                try:
                    results = model(frame, verbose=False) # Run YOLO inference
                    if results and results[0].boxes:
                        latest_detections = results[0].boxes.data.cpu().numpy() # Update detections
                        # Check for crash class
                        if 0.0 in latest_detections[:, -1]: # Check class ID in last column
                            crash_detected_in_video = True
                            # logger.info(f"Crash detected frame {frame_count}") # Log less frequently if needed
                    else:
                        latest_detections = [] # Clear if no detections this frame
                except Exception as e:
                    logger.error(f"Error during YOLO inference on frame {frame_count}: {e}")
                    latest_detections = [] # Clear detections on error

            # --- Draw Latest Detections onto the Display Frame ---
            # Draw boxes from the *most recent* successful YOLO run
            for det in latest_detections:
                try:
                    x1, y1, x2, y2, conf, cls_id = det
                    cls_id = int(cls_id)
                    label = f"{class_names.get(cls_id, f'CLS_{cls_id}')}: {conf:.2f}"
                    color = (0, 0, 255) if cls_id == 0 else (0, 255, 0) # Red for crash (Class ID 0)

                    # Draw rectangle
                    cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    # Draw label background
                    (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    cv2.rectangle(display_frame, (int(x1), int(y1) - h - 5), (int(x1) + w, int(y1)), color, -1)
                    # Draw label text (white on colored background)
                    cv2.putText(display_frame, label, (int(x1), int(y1) - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                except Exception as draw_err:
                    logger.warning(f"Error drawing detection data {det}: {draw_err}")


            # --- Push Frame (with drawn boxes) to Backend Stream ---
            if frame_count % frame_skip_push == 0:
                try:
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
                    # Encode the frame *with boxes drawn on it*
                    result, encoded_jpeg = cv2.imencode('.jpg', display_frame, encode_param)
                    if result:
                        if push_frame_to_backend(encoded_jpeg.tobytes()):
                            frames_pushed_count += 1
                    # else: logger.warning(f"Failed encode frame {frame_count}") # Noisy
                except Exception as e:
                    logger.error(f"Error encoding/pushing drawn frame {frame_count}: {e}")

            # Check if crash was detected in the video overall (for logging/notification)
            if crash_detected_in_video and frame_count % 60 == 0: # Log detection periodically
                 logger.info(f"Crash previously detected in video, continuing analysis/stream (Frame {frame_count})")


    finally:
        # --- Cleanup ---
        cap.release()
        total_time = time.time() - overall_start_time
        logger.info(f"Finished analyzing {video_path.name}. Crash detected: {crash_detected_in_video}. Total time: {total_time:.2f}s")
        logger.info(f"Frames processed by YOLO: {yolo_processed_count}. Frames pushed to stream: {frames_pushed_count}.")
        clear_backend_stream_buffer() # Signal backend to clear

    return crash_detected_in_video

# --- File Processing Loop --- (Remains the same)
def process_files():
    logger.debug(f"Checking for videos in {INPUT_DIR}...")
    processed_a_file = False
    videos_to_process = list(INPUT_DIR.glob("*.mp4"))
    if not videos_to_process: return

    for video_path in videos_to_process:
        processed_a_file = True
        logger.info(f"--- Processing video: {video_path.name} ---")
        try:
            analysis_result = analyze_video(video_path) # Calls version that draws & pushes
            if analysis_result is True: # Crash detected
                dest_path = CRASH_DIR / video_path.name
                try:
                    CRASH_DIR.mkdir(parents=True, exist_ok=True)
                    video_path.rename(dest_path)
                    logger.info(f"✅ Moved crash video to: {dest_path}")
                    logger.info(f"🚨 Crash detected in {video_path.name}. Sending notification...")
                    send_crash_notification_to_backend(video_path.name)
                except OSError as e: logger.error(f"⚠️ Error moving file {video_path.name}: {e}")
                except Exception as e: logger.error(f"⚠️ Error handling crash video {video_path.name}: {e}")
            elif analysis_result is False: # No crash
                try: video_path.unlink(); logger.info(f"❌ Deleted non-crash video: {video_path.name}")
                except OSError as e: logger.error(f"⚠️ Error deleting file {video_path.name}: {e}")
                except Exception as e: logger.error(f"⚠️ Unexpected error deleting non-crash video: {e}")
            else: logger.error(f"⚠️ Analysis failed for {video_path.name}, not moved/deleted.")
        except Exception as e: logger.error(f"⚠️ Unhandled error during processing loop for {video_path.name}: {str(e)}", exc_info=True); continue
    # if processed_a_file: logger.debug("Finished processing cycle.")

# --- Main Execution --- (Remains the same)
if __name__ == "__main__":
    logger.info("--- Starting AI Crash Detector Script (Stream w/ Boxes) ---") # Updated log
    logger.info(f"Watching directory: {INPUT_DIR}")
    logger.info(f"Crash videos will be moved to: {CRASH_DIR}")
    logger.info(f"Notifications will be sent to: {CRASH_API_URL}")
    logger.info(f"Video frames (with boxes) will be pushed to: {FRAME_PUSH_URL}") # Updated log

    try: CRASH_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: logger.error(f"Could not create crash directory {CRASH_DIR}: {e}"); exit()

    while True:
        try: process_files(); time.sleep(5)
        except KeyboardInterrupt: logger.info("Ctrl+C detected. Shutting down."); break
        except Exception as e: logger.error(f"An unexpected error in main loop: {e}", exc_info=True); logger.info("Restarting loop after 15s..."); time.sleep(15)
    logger.info("--- AI Crash Detector Script Stopped ---")
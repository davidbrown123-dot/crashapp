import cv2
from pathlib import Path
import time
import requests
from ultralytics import YOLO
import os

# Paths (match your Windows directory)
INPUT_DIR = Path("C:\Users\Abderrahmen\Desktop\captures\pollution")
CRASH_DIR = INPUT_DIR / "Crashes"

# Blynk Settings
BLYNK_AUTH_TOKEN = "YourESP32sBlynkAuthToken"  # Replace with your ESP32's token!
BLYNK_API_URL = f"https://blynk.cloud/external/api/log?token={BLYNK_AUTH_TOKEN}&message=🚨 CRASH DETECTED!"

# Load your custom YOLOv12 model
model = YOLO("best.pt")  # Your trained weights

def send_blynk_alert():
    """Send notification to Blynk app."""
    try:
        response = requests.get(BLYNK_API_URL, timeout=5)  # Added timeout
        response.raise_for_status()  # Raises exception for HTTP errors
        print("Blynk alert sent successfully!")
    except Exception as e:
        print(f"⚠️ Blynk alert failed: {str(e)}")

def analyze_video(video_path):
    """Analyze video frames for crashes with frame skipping for efficiency."""
    cap = cv2.VideoCapture(str(video_path))
    crash_detected = False
    frame_skip = 3  # Process every 5th frame (adjust based on needs)
    frame_count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        if frame_count % frame_skip != 0:
            continue  # Skip frames for faster processing
        
        # YOLOv12 Inference
        results = model(frame, verbose=False)
        
        # Check for crash class (replace 0 with your crash class ID)
        if 1 in results[0].boxes.cls:
            crash_detected = True
            break
    
    cap.release()
    return crash_detected

def process_files():
    """Process new videos and delete non-crash files."""
    for video in INPUT_DIR.glob("*.mp4"):
        try:
            if analyze_video(video):
                # Move crash videos
                dest = CRASH_DIR / video.name
                dest.parent.mkdir(exist_ok=True)
                video.rename(dest)
                print(f"🚨 Crash detected in {video.name}")
                send_blynk_alert()
            else:
                # Delete non-crash videos immediately
                video.unlink()
                print(f"❌ Deleted non-crash video: {video.name}")
                
        except Exception as e:
            print(f"⚠️ Error processing {video.name}: {str(e)}")
            continue

if __name__ == "__main__":
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    
    while True:
        process_files()
        time.sleep(5)  # Check every 5 seconds
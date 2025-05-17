# backend/app/video_stream_buffer.py
import asyncio
import logging

logger = logging.getLogger(__name__)

# Simple approach using a global variable protected by a lock
# Stores the latest received JPEG frame bytes
latest_frame_bytes_global: bytes | None = None
lock = asyncio.Lock() # Protect access to the global variable

async def update_frame_global(new_frame_bytes: bytes):
    """ Updates the globally stored latest frame bytes. """
    global latest_frame_bytes_global
    async with lock:
        latest_frame_bytes_global = new_frame_bytes
        # logger.debug("Global frame updated") # Can be noisy

async def get_latest_frame_global() -> bytes | None:
    """ Gets the latest globally stored frame bytes. """
    global latest_frame_bytes_global
    async with lock:
        # logger.debug("Getting global frame")
        return latest_frame_bytes_global

async def clear_frame_global():
    """ Clears the stored frame (e.g., when analysis stops). """
    global latest_frame_bytes_global
    async with lock:
        latest_frame_bytes_global = None
        logger.info("Global frame buffer cleared.")
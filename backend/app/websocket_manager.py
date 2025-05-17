# backend/app/websocket_manager.py
from fastapi import WebSocket
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        """Broadcasts a message (as JSON) to all connected clients."""
        disconnected_clients = []
        message_json = json.dumps(message) # Pre-serialize the message
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                # Handle cases where connection might be broken but not yet removed
                logger.warning(f"Failed to send message to a client: {e}. Marking for removal.")
                disconnected_clients.append(connection)

        # Clean up disconnected clients found during broadcast
        for client in disconnected_clients:
            self.disconnect(client)

    async def broadcast_crash_notification(self, crash_data: Dict):
        """Specific method to broadcast a crash notification."""
        await self.broadcast({
            "type": "new_crash",
            "data": crash_data # e.g., {"timestamp": "...", "video_filename": "..."}
        })
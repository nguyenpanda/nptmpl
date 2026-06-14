import logging
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any

logger = logging.getLogger("nptmpl.server.ws")

class ConnectionManager:
    """Manages active WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        headers = dict(websocket.scope.get("headers", []))
        decoded_headers = {k.decode(): v.decode() for k, v in headers.items()}
        logger.info(f"WebSocket handshake headers: {decoded_headers}")
        
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Sends a message to all connected clients."""
        logger.debug(f"Broadcasting: {message}")
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                disconnected.append(connection)
        
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

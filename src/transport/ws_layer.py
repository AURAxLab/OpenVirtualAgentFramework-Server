import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from structlog import get_logger
from typing import List

from src.transport.base import BaseTransport

logger = get_logger()

class WebSocketTransport(BaseTransport):
    """
    WebSocket Bidirectional Transport integrated via FastAPI Router.
    Allows Web, Mobile and Wizard-of-Oz clients to connect and send/receive commands.
    """
    def __init__(self):
        super().__init__()
        # Keep track of active websocket connections
        self.active_connections: List[WebSocket] = []
        
    async def start(self):
        # WebSocket server doesn't bind a port directly here.
        # It relies on the main FastAPI application to mount its endpoints
        # and trigger the connection manager methods.
        logger.info("WebSocket Transport initialized (Awaiting FastAPI mount).")
        
    async def stop(self):
        logger.info("Stopping WebSocket Transport...")
        for connection in self.active_connections:
            await connection.close(code=1001, reason="Server shutting down")
        self.active_connections.clear()
        logger.info("WebSocket Transport stopped.")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected", total_connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected", total_connections=len(self.active_connections))

    async def handle_incoming(self, websocket: WebSocket):
        """Loop to read incoming messages from a specific active connecton"""
        try:
            while True:
                data = await websocket.receive_text()
                # Dispatch up to the framework
                await self._dispatch_message(data)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.error("WebSocket Listener error", error=str(e))
            self.disconnect(websocket)

    async def publish(self, topic: str, message: str):
        """
        Broadcasts the message to all connected WebSocket clients.
        Sends as JSON string format depending on the architecture needs, wrapper with topic.
        """
        if not self.active_connections:
            return
            
        # Optional: We wrap the raw message in a small JSON envelope containing the topic
        # so frontend clients know how to route it internally.
        payload = f'{{"topic": "{topic}", "payload": {message}}}'
        
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error("Failed to send WS message", error=str(e))
                dead_connections.append(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

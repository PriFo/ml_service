"""WebSocket endpoint for real-time updates"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connections"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit event to all connected clients"""
        message = {
            "type": event_type,
            "payload": payload,
            "timestamp": json.dumps(datetime.now().isoformat())
        }
        await self.broadcast(message)


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                event_type = message.get("type")
                payload = message.get("payload", {})
                
                # Handle client events
                if event_type == "queue:subscribe":
                    # Subscribe to queue updates
                    await manager.send_personal_message({
                        "type": "queue:subscribed",
                        "payload": {"status": "ok"}
                    }, websocket)
                
                elif event_type == "alerts:acknowledge":
                    # Acknowledge alert
                    await manager.send_personal_message({
                        "type": "alerts:acknowledged",
                        "payload": {"status": "ok"}
                    }, websocket)
                
                else:
                    logger.warning(f"Unknown event type: {event_type}")
            
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


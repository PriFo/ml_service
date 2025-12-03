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
            if websocket.client_state.name == "CONNECTED":
                await websocket.send_json(message)
        except Exception as e:
            # Only log if it's not a normal disconnection
            if "not connected" not in str(e).lower() and "closed" not in str(e).lower():
                logger.warning(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connections"""
        disconnected = []
        for connection in self.active_connections:
            try:
                # Check if connection is still active
                if connection.client_state.name == "CONNECTED":
                    await connection.send_json(message)
                else:
                    disconnected.append(connection)
            except Exception as e:
                # Only log if it's not a normal disconnection
                if "not connected" not in str(e).lower() and "closed" not in str(e).lower():
                    logger.debug(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit event to all connected clients"""
        message = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_job_progress(self, job_id: str, current: int, total: int):
        """Send job progress update to all clients"""
        percent = int((current / total * 100)) if total > 0 else 0
        message = {
            "type": "job:progress",
            "job_id": job_id,
            "progress": {
                "current": current,
                "total": total,
                "percent": percent
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_job_status(self, job_id: str, status: str, job_data: Dict[str, Any] = None):
        """Send job status update to all clients"""
        message = {
            "type": "job:status",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        if job_data:
            message["job"] = job_data
        await self.broadcast(message)
    
    async def send_to_job_subscribers(self, job_id: str, message: Dict[str, Any]):
        """Send message to clients subscribed to specific job"""
        # For now, broadcast to all (can be optimized with subscription tracking)
        message["job_id"] = job_id
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


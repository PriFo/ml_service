"""Event emitter for creating and broadcasting events"""
import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any

from ml_service.db.repositories import EventRepository
from ml_service.db.models import Event, Job
from ml_service.api.websocket import manager as ws_manager

logger = logging.getLogger(__name__)


def emit_event(
    job: Job,
    event_type: str,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    stage: Optional[str] = None
) -> Event:
    """
    Create and emit an event.
    
    Args:
        job: Job object
        event_type: Type of event ('created', 'started', 'progress', 'completed', 'failed')
        input_data: Input data dictionary
        output_data: Output data dictionary
        error: Error message if any
        stage: Current stage of processing
    
    Returns: Created Event object
    """
    event_repo = EventRepository()
    
    # Calculate duration if job has started_at
    duration_ms = None
    if job.started_at and event_type in ('completed', 'failed'):
        duration = datetime.now() - job.started_at
        duration_ms = int(duration.total_seconds() * 1000)
    
    # Calculate data size
    data_size_bytes = None
    if input_data:
        data_size_bytes = len(json.dumps(input_data).encode('utf-8'))
    elif output_data:
        data_size_bytes = len(json.dumps(output_data).encode('utf-8'))
    
    # Create event
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        source=job.source,
        model_key=job.model_key,
        status=job.status,
        stage=stage or job.stage,
        input_data=json.dumps(input_data) if input_data else None,
        output_data=json.dumps(output_data) if output_data else None,
        user_agent=job.user_agent,
        client_ip=job.client_ip,
        created_at=datetime.now(),
        completed_at=datetime.now() if event_type in ('completed', 'failed') else None,
        error_message=error,
        duration_ms=duration_ms,
        display_format="table",
        data_size_bytes=data_size_bytes
    )
    
    # Save to database
    event_repo.create(event)
    
    # Send via WebSocket
    try:
        ws_manager.broadcast({
            "type": "event:new",
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "model_key": event.model_key,
                "status": event.status,
                "stage": event.stage,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "duration_ms": event.duration_ms,
                "data_size_bytes": event.data_size_bytes
            }
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast event via WebSocket: {e}")
    
    return event


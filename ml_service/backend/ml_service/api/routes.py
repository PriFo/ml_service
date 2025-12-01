"""API routes"""
import uuid
import time
import asyncio
import ast
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
import json

logger = logging.getLogger(__name__)

from fastapi import WebSocket
from ml_service.api.models import (
    TrainingRequest, TrainingResponse,
    PredictionRequest, PredictionResponse, PredictionItem,
    PredictionJobResponse, PredictionResultResponse,
    QualityRequest, QualityResponse,
    ModelsResponse, ModelInfo,
    AlertsResponse, AlertInfo,
    DriftReportsResponse, DriftReport,
    EventsResponse, EventInfo,
    JobsResponse, JobInfo
)
from ml_service.api.deps import AuthDep
from ml_service.api.websocket import websocket_endpoint, manager
from ml_service.db.repositories import (
    ModelRepository, JobRepository, TrainingJobRepository, AlertRepository, 
    DriftCheckRepository, PredictionLogRepository, EventRepository
)
from ml_service.db.models import PredictionLog, Event, Job
from ml_service.ml.model import MLModel
from ml_service.ml.validators import DataValidator
from ml_service.core.config import settings
from ml_service.core.request_source import detect_request_source, get_client_ip, get_user_agent
from ml_service.db.models import Model

router = APIRouter()


# Training queue (in-memory for now, should be Redis in production)
training_queue = []
training_jobs = {}


def safe_parse_feature_fields(feature_fields_str: Optional[str]) -> List[str]:
    """Safely parse feature_fields from string to list"""
    if not feature_fields_str:
        return []
    
    try:
        # Try JSON first
        result = json.loads(feature_fields_str)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    
    try:
        # Try Python literal eval (for string representations like "['field1', 'field2']")
        result = ast.literal_eval(feature_fields_str)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        pass
    
    # If all parsing fails, return empty list
    return []


async def process_training_job(job_id: str, request: TrainingRequest, event_id: Optional[str] = None):
    """Background task to process training job"""
    job_repo = JobRepository()
    model_repo = ModelRepository()
    event_repo = EventRepository() if event_id else None
    
    try:
        logger.info(f"Starting training job {job_id} for model {request.model_key} v{request.version}")
        # Update status to running
        job_repo.update_status(job_id, "running", stage="training")
        if event_repo and event_id:
            event_repo.update_status(event_id, "running", stage="training")
        
        # Create model instance
        features_config = {
            "feature_fields": request.feature_fields,
            "target_field": request.target_field
        }
        
        model = MLModel(
            model_key=request.model_key,
            version=request.version,
            features_config=features_config
        )
        
        # Train model
        metrics = model.train(
            items=request.items,
            target_field=request.target_field,
            feature_fields=request.feature_fields,
            validation_split=request.validation_split,
            use_gpu=request.use_gpu_if_available
        )
        
        # Save model to database
        db_model = Model(
            model_key=request.model_key,
            version=request.version,
            status="active",
            accuracy=metrics.get("validation_accuracy"),
            created_at=datetime.now(),
            last_trained=datetime.now(),
            task_type=request.task_type,
            target_field=request.target_field,
            feature_fields=str(request.feature_fields)
        )
        model_repo.create(db_model)
        
        # Update job status
        job_repo.update_status(job_id, "completed", metrics=metrics, stage="completed")
        if event_repo and event_id:
            event_repo.update_status(
                event_id, 
                "completed", 
                stage="completed",
                output_data=json.dumps(metrics)
            )
        
    except Exception as e:
        logger.error(f"Training job {job_id} failed: {e}", exc_info=True)
        error_msg = str(e)
        # Truncate very long error messages
        if len(error_msg) > 1000:
            error_msg = error_msg[:1000] + "... (truncated)"
        job_repo.update_status(job_id, "failed", error_message=error_msg, stage="failed")
        if event_repo and event_id:
            event_repo.update_status(
                event_id,
                "failed",
                stage="failed",
                error_message=error_msg
            )
        # Don't re-raise to prevent background task from crashing


async def process_predict_job(job_id: str, request: PredictionRequest, event_id: Optional[str] = None):
    """Background task to process prediction job"""
    job_repo = JobRepository()
    model_repo = ModelRepository()
    event_repo = EventRepository() if event_id else None
    
    start_time = time.time()
    
    try:
        logger.info(f"Starting prediction job {job_id} for model {request.model_key}")
        # Update status to running
        job_repo.update_status(job_id, "running", stage="loading_model")
        if event_repo and event_id:
            event_repo.update_status(event_id, "running", stage="loading_model")
        
        # Get model
        model = model_repo.get(request.model_key, request.version)
        if not model:
            raise ValueError("Model not found")
        
        # Load model
        job_repo.update_status(job_id, "running", stage="loading_model")
        features_config = {
            "feature_fields": safe_parse_feature_fields(model.feature_fields),
            "target_field": model.target_field or ""
        }
        
        ml_model = MLModel(
            model_key=request.model_key,
            version=request.version or model.version,
            features_config=features_config
        )
        
        try:
            ml_model._load_model()
        except Exception as e:
            logger.error(f"Failed to load model {request.model_key} v{request.version or model.version}: {e}")
            raise ValueError(f"Failed to load model: {str(e)}")
        
        # Validate data
        job_repo.update_status(job_id, "running", stage="validating")
        if event_repo and event_id:
            event_repo.update_status(event_id, "running", stage="validating")
        
        validator = DataValidator(
            feature_fields=features_config["feature_fields"],
            target_field=None
        )
        valid_items, invalid_items = validator.validate_prediction_data(request.data, strict=False)
        
        if not valid_items:
            raise ValueError(f"No valid items for prediction. Total items: {len(request.data)}, Invalid: {len(invalid_items)}")
        
        # Make predictions
        job_repo.update_status(job_id, "running", stage="predicting")
        if event_repo and event_id:
            event_repo.update_status(event_id, "running", stage="predicting")
        
        try:
            # Prepare features first for logging
            X_features = None
            try:
                X_features = ml_model._prepare_features(valid_items, fit=False)
            except Exception as feature_error:
                logger.warning(f"Failed to prepare features for logging: {feature_error}")
            
            # Make predictions
            predictions = ml_model.predict(valid_items)
            
            # Log predictions for drift detection
            try:
                log_repo = PredictionLogRepository()
                import pickle
                
                for i, pred in enumerate(predictions):
                    if X_features is not None and i < X_features.shape[0]:
                        item_features = X_features[i:i+1]
                        feature_bytes = pickle.dumps(item_features)
                    else:
                        feature_bytes = None
                    
                    log = PredictionLog(
                        log_id=str(uuid.uuid4()),
                        model_key=request.model_key,
                        version=request.version or model.version,
                        input_features=feature_bytes,
                        prediction=pred.get("prediction"),
                        confidence=pred.get("confidence"),
                        created_at=datetime.now()
                    )
                    log_repo.create(log)
            except Exception as log_error:
                logger.warning(f"Failed to log prediction for drift detection: {log_error}")
        
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error during prediction: {e}", exc_info=True)
            raise ValueError(f"Prediction failed: {str(e)}")
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Prepare result data - predictions are already dicts
        result_data = {
            "predictions": predictions,  # Already in correct format
            "processing_time_ms": processing_time,
            "unexpected_items": invalid_items if invalid_items else None
        }
        
        # Update job status with results
        job_repo.update_status(job_id, "completed", metrics=result_data, stage="completed")
        if event_repo and event_id:
            event_repo.update_status(
                event_id,
                "completed",
                stage="completed",
                output_data=json.dumps({
                    "predictions_count": len(predictions),
                    "processing_time_ms": processing_time,
                    "invalid_items_count": len(invalid_items) if invalid_items else 0
                })
            )
        
    except Exception as e:
        logger.error(f"Prediction job {job_id} failed: {e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 1000:
            error_msg = error_msg[:1000] + "... (truncated)"
        job_repo.update_status(job_id, "failed", error_message=error_msg, stage="failed")
        if event_repo and event_id:
            event_repo.update_status(
                event_id,
                "failed",
                stage="failed",
                error_message=error_msg
            )
        # Don't re-raise to prevent background task from crashing


@router.post("/train", response_model=TrainingResponse)
async def train_model(
    request: TrainingRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    user: dict = AuthDep
):
    """Start training a new model"""
    try:
        job_id = f"train_{uuid.uuid4().hex[:8]}"
        
        # Get request metadata
        source = detect_request_source(http_request)
        client_ip = get_client_ip(http_request)
        user_agent = get_user_agent(http_request)
        
        # Create job with metadata
        job = Job(
            job_id=job_id,
            model_key=request.model_key,
            job_type="train",
            status="queued",
            stage="queued",
            source=source,
            dataset_size=len(request.items),
            created_at=datetime.now(),
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        job_repo = JobRepository()
        job_repo.create(job)
        
        # Log event
        event_repo = EventRepository()
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type="train",
            source=source,
            model_key=request.model_key,
            status="queued",
            stage="queued",
            input_data=json.dumps({
                "model_key": request.model_key,
                "version": request.version,
                "items_count": len(request.items),
                "feature_fields": request.feature_fields,
                "target_field": request.target_field
            }),
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=datetime.now()
        )
        event_repo.create(event)
        
        # Add to background tasks
        background_tasks.add_task(process_training_job, job_id, request, event.event_id)
        
        # Estimate time (rough estimate: 1 second per 1000 samples)
        estimated_time = max(60, len(request.items) // 1000)
        
        return TrainingResponse(
            job_id=job_id,
            status="queued",
            model_key=request.model_key,
            version=request.version,
            estimated_time=estimated_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting training job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start training job: {str(e)}"
        )


@router.post("/predict", response_model=PredictionJobResponse)
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    user: dict = AuthDep
):
    """Start prediction job (async)"""
    try:
        job_id = f"predict_{uuid.uuid4().hex[:8]}"
        
        # Get request metadata
        source = detect_request_source(http_request)
        client_ip = get_client_ip(http_request)
        user_agent = get_user_agent(http_request)
        
        # Verify model exists
        model_repo = ModelRepository()
        model = model_repo.get(request.model_key, request.version)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Create job with metadata
        job = Job(
            job_id=job_id,
            model_key=request.model_key,
            job_type="predict",
            status="queued",
            stage="queued",
            source=source,
            dataset_size=len(request.data),
            created_at=datetime.now(),
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        job_repo = JobRepository()
        job_repo.create(job)
        
        # Log event
        event_repo = EventRepository()
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type="predict",
            source=source,
            model_key=request.model_key,
            status="queued",
            stage="queued",
            input_data=json.dumps({
                "model_key": request.model_key,
                "version": request.version,
                "data_count": len(request.data)
            }),
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=datetime.now()
        )
        event_repo.create(event)
        
        # Add to background tasks
        background_tasks.add_task(process_predict_job, job_id, request, event.event_id)
        
        # Estimate time (rough estimate: 100ms per item)
        estimated_time = max(5, len(request.data) // 10)
        
        return PredictionJobResponse(
            job_id=job_id,
            status="queued",
            model_key=request.model_key,
            version=request.version or model.version,
            estimated_time=estimated_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting prediction job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start prediction job: {str(e)}"
        )


@router.get("/predict/{job_id}", response_model=PredictionResultResponse)
async def get_predict_result(job_id: str, user: dict = AuthDep):
    """Get prediction job results"""
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.job_type != "predict":
        raise HTTPException(status_code=400, detail="Job is not a prediction job")
    
    # Parse results from metrics if job is completed
    predictions = None
    processing_time_ms = None
    unexpected_items = None
    
    if job.status == "completed" and job.metrics:
        try:
            result_data = json.loads(job.metrics)
            predictions = [PredictionItem(**p) for p in result_data.get("predictions", [])]
            processing_time_ms = result_data.get("processing_time_ms")
            unexpected_items = result_data.get("unexpected_items")
        except Exception as e:
            logger.error(f"Failed to parse prediction results: {e}")
    
    return PredictionResultResponse(
        job_id=job.job_id,
        status=job.status,
        predictions=predictions,
        processing_time_ms=processing_time_ms,
        unexpected_items=unexpected_items,
        error_message=job.error_message
    )


@router.post("/quality", response_model=QualityResponse)
async def check_quality(
    request: QualityRequest,
    user: dict = AuthDep
):
    """Check model quality metrics"""
    model_repo = ModelRepository()
    model = model_repo.get(request.model_key, request.version)
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # In production, this would evaluate on test set
    # For now, return stored metrics
    return QualityResponse(
        model_key=request.model_key,
        version=model.version,
        metrics={
            "accuracy": model.accuracy or 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0
        },
        samples_analyzed=0,
        last_updated=model.last_trained or model.created_at or datetime.now()
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models(user: dict = AuthDep):
    """List all models"""
    model_repo = ModelRepository()
    models = model_repo.get_all()
    
    # Group by model_key
    model_dict = {}
    for model in models:
        if model.model_key not in model_dict:
            model_dict[model.model_key] = {
                "versions": [],
                "active_version": model.version,
                "status": model.status,
                "accuracy": model.accuracy,
                "last_trained": model.last_trained
            }
        model_dict[model.model_key]["versions"].append(model.version)
    
    model_infos = [
        ModelInfo(
            model_key=key,
            versions=info["versions"],
            active_version=info["active_version"],
            status=info["status"],
            accuracy=info["accuracy"],
            last_trained=info["last_trained"]
        )
        for key, info in model_dict.items()
    ]
    
    return ModelsResponse(models=model_infos)


@router.get("/health/alerts", response_model=AlertsResponse)
async def get_alerts(user: dict = AuthDep):
    """Get active alerts"""
    alert_repo = AlertRepository()
    alerts = alert_repo.get_active()
    
    alert_infos = [
        AlertInfo(
            alert_id=alert.alert_id,
            type=alert.type,
            severity=alert.severity,
            model_key=alert.model_key,
            message=alert.message,
            details=json.loads(alert.details) if alert.details else None,
            created_at=alert.created_at or datetime.now(),
            dismissible=True
        )
        for alert in alerts
    ]
    
    return AlertsResponse(alerts=alert_infos)


@router.post("/health/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str, user: dict = AuthDep):
    """Dismiss an alert"""
    alert_repo = AlertRepository()
    success = alert_repo.dismiss(alert_id, dismissed_by=user.get("token", "unknown"))
    
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"status": "dismissed"}


@router.post("/drift/check")
async def check_drift(
    request: TrainingRequest,
    http_request: Request,
    user: dict = AuthDep
):
    """Check drift for a dataset (user-initiated)"""
    event_id = str(uuid.uuid4())
    event_repo = EventRepository()
    
    # Get request metadata
    source = detect_request_source(http_request)
    client_ip = get_client_ip(http_request)
    user_agent = get_user_agent(http_request)
    
    # Log event start
    event = Event(
        event_id=event_id,
        event_type="drift",
        source=source,
        model_key=request.model_key,
        status="running",
        stage="checking",
        input_data=json.dumps({
            "model_key": request.model_key,
            "items_count": len(request.items)
        }),
        client_ip=client_ip,
        user_agent=user_agent,
        created_at=datetime.now()
    )
    event_repo.create(event)
    
    try:
        from ml_service.ml.drift_detector import DriftDetector
        
        drift_detector = DriftDetector()
        
        # Get model version
        model_repo = ModelRepository()
        model = model_repo.get(request.model_key)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Check drift
        drift_result = await drift_detector.check_drift(
            model_key=request.model_key,
            version=model.version
        )
        
        # Save drift check result
        drift_repo = DriftCheckRepository()
        drift_repo.create_drift_check(
            model_key=request.model_key,
            check_date=datetime.now().date(),
            psi_value=drift_result.get("psi"),
            js_divergence=drift_result.get("js_divergence"),
            drift_detected=drift_result.get("drift_detected", False),
            items_analyzed=drift_result.get("items_analyzed", 0)
        )
        
        # Update event with result
        event_repo.update_status(
            event_id,
            "completed",
            stage="completed",
            output_data=json.dumps(drift_result)
        )
        
        return drift_result
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Drift check failed: {e}", exc_info=True)
        event_repo.update_status(
            event_id,
            "failed",
            stage="failed",
            error_message=error_msg[:1000] if len(error_msg) > 1000 else error_msg
        )
        raise HTTPException(
            status_code=500,
            detail=f"Drift check failed: {str(e)}"
        )


@router.get("/drift/daily-reports", response_model=DriftReportsResponse)
async def get_drift_reports(
    model_key: Optional[str] = None,
    limit: int = 30,
    user: dict = AuthDep
):
    """Get drift check reports"""
    drift_repo = DriftCheckRepository()
    
    if model_key:
        reports = drift_repo.get_drift_history(model_key, limit)
    else:
        # Get all drift reports (simplified)
        reports = []
    
    report_infos = [
        DriftReport(
            check_id=report.check_id,
            model_key=report.model_key,
            check_date=report.check_date.isoformat(),
            psi_value=report.psi_value,
            js_divergence=report.js_divergence,
            drift_detected=report.drift_detected,
            items_analyzed=report.items_analyzed,
            created_at=report.created_at or datetime.now()
        )
        for report in reports
    ]
    
    return DriftReportsResponse(reports=report_infos)


@router.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_endpoint(websocket)


@router.get("/health")
async def health_check():
    """Health check endpoint (no auth required)"""
    return {
        "status": "healthy",
        "version": "0.9.1",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/events", response_model=EventsResponse)
async def get_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    client_ip: Optional[str] = None,
    limit: int = 50,
    user: dict = AuthDep
):
    """Get all events with optional filters"""
    event_repo = EventRepository()
    events = event_repo.get_all(
        limit=limit,
        event_type=event_type,
        source=source,
        status=status,
        client_ip=client_ip
    )
    
    event_infos = [
        EventInfo(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            model_key=event.model_key,
            status=event.status,
            stage=event.stage,
            input_data=json.loads(event.input_data) if event.input_data else None,
            output_data=json.loads(event.output_data) if event.output_data else None,
            user_agent=event.user_agent,
            client_ip=event.client_ip,
            created_at=event.created_at or datetime.now(),
            completed_at=event.completed_at,
            error_message=event.error_message
        )
        for event in events
    ]
    
    return EventsResponse(events=event_infos)


@router.get("/events/{event_id}", response_model=EventInfo)
async def get_event(event_id: str, user: dict = AuthDep):
    """Get event details"""
    event_repo = EventRepository()
    event = event_repo.get(event_id)
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return EventInfo(
        event_id=event.event_id,
        event_type=event.event_type,
        source=event.source,
        model_key=event.model_key,
        status=event.status,
        stage=event.stage,
        input_data=json.loads(event.input_data) if event.input_data else None,
        output_data=json.loads(event.output_data) if event.output_data else None,
        user_agent=event.user_agent,
        client_ip=event.client_ip,
        created_at=event.created_at or datetime.now(),
        completed_at=event.completed_at,
        error_message=event.error_message
    )


@router.get("/events/suspicious", response_model=EventsResponse)
async def get_suspicious_events(
    limit: int = 50,
    user: dict = AuthDep
):
    """Get suspicious events (multiple events from same IP)"""
    event_repo = EventRepository()
    events = event_repo.get_suspicious_events(limit=limit)
    
    event_infos = [
        EventInfo(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            model_key=event.model_key,
            status=event.status,
            stage=event.stage,
            input_data=json.loads(event.input_data) if event.input_data else None,
            output_data=json.loads(event.output_data) if event.output_data else None,
            user_agent=event.user_agent,
            client_ip=event.client_ip,
            created_at=event.created_at or datetime.now(),
            completed_at=event.completed_at,
            error_message=event.error_message
        )
        for event in events
    ]
    
    return EventsResponse(events=event_infos)


@router.get("/events/by-ip/{ip}", response_model=EventsResponse)
async def get_events_by_ip(
    ip: str,
    limit: int = 50,
    user: dict = AuthDep
):
    """Get all events from a specific IP address"""
    event_repo = EventRepository()
    events = event_repo.get_by_ip(ip, limit=limit)
    
    event_infos = [
        EventInfo(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            model_key=event.model_key,
            status=event.status,
            stage=event.stage,
            input_data=json.loads(event.input_data) if event.input_data else None,
            output_data=json.loads(event.output_data) if event.output_data else None,
            user_agent=event.user_agent,
            client_ip=event.client_ip,
            created_at=event.created_at or datetime.now(),
            completed_at=event.completed_at,
            error_message=event.error_message
        )
        for event in events
    ]
    
    return EventsResponse(events=event_infos)


@router.get("/jobs/{job_id}", response_model=JobInfo)
async def get_job_status(job_id: str, user: dict = AuthDep):
    """Get job status (supports all job types)"""
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobInfo(
        job_id=job.job_id,
        model_key=job.model_key,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        source=job.source,
        dataset_size=job.dataset_size,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metrics=json.loads(job.metrics) if job.metrics else None,
        error_message=job.error_message,
        client_ip=job.client_ip,
        user_agent=job.user_agent
    )


@router.get("/jobs", response_model=JobsResponse)
async def list_jobs(
    model_key: Optional[str] = None,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
    user: dict = AuthDep
):
    """List jobs (supports all job types: train, predict, drift, other)"""
    job_repo = JobRepository()
    
    if model_key:
        jobs = job_repo.get_by_model(model_key, limit)
    elif status:
        jobs = job_repo.get_by_status(status, limit)
    else:
        jobs = job_repo.get_all(limit, job_type=job_type)
    
    job_infos = [
        JobInfo(
            job_id=job.job_id,
            model_key=job.model_key,
            job_type=job.job_type,
            status=job.status,
            stage=job.stage,
            source=job.source,
            dataset_size=job.dataset_size,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            metrics=json.loads(job.metrics) if job.metrics else None,
            error_message=job.error_message,
            client_ip=job.client_ip,
            user_agent=job.user_agent
        )
        for job in jobs
    ]
    
    return JobsResponse(jobs=job_infos)


@router.get("/models/{model_key}")
async def get_model_details(
    model_key: str,
    version: Optional[str] = None,
    user: dict = AuthDep
):
    """Get detailed model information"""
    model_repo = ModelRepository()
    model = model_repo.get(model_key, version)
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get all versions of this model
    all_models = model_repo.get_all()
    versions = [
        {
            "version": m.version,
            "status": m.status,
            "accuracy": m.accuracy,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "last_trained": m.last_trained.isoformat() if m.last_trained else None,
            "task_type": m.task_type,
            "target_field": m.target_field,
            "feature_fields": safe_parse_feature_fields(m.feature_fields)
        }
        for m in all_models if m.model_key == model_key
    ]
    
    # Get training jobs for this model
    job_repo = TrainingJobRepository()
    jobs = job_repo.get_by_model(model_key, 10)
    
    return {
        "model_key": model_key,
        "current_version": model.version,
        "versions": versions,
        "recent_jobs": [
            {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message
            }
            for job in jobs
        ]
    }


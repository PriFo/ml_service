"""API routes"""
import uuid
import time
import asyncio
import ast
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Header
import json

logger = logging.getLogger(__name__)

from fastapi import WebSocket, WebSocketDisconnect
from ml_service.api.models import (
    TrainingRequest, TrainingResponse,
    PredictionRequest, PredictionResponse, PredictionItem,
    PredictionJobResponse, PredictionResultResponse,
    QualityRequest, QualityResponse,
    ModelsResponse, ModelInfo,
    AlertsResponse, AlertInfo,
    DriftReportsResponse, DriftReport,
    EventsResponse, EventInfo,
    JobsResponse, JobInfo,
    RetrainingRequest,
    LoginRequest, LoginResponse,
    RegisterRequest, RegisterResponse,
    CreateUserRequest, UserInfo, UsersResponse,
    ChangePasswordRequest, ChangeUsernameRequest, UserProfileResponse,
    CreateTokenRequest, TokenInfo, TokenResponse, TokensResponse
)
from ml_service.api.deps import AuthDep
from ml_service.api.websocket import websocket_endpoint, manager
from ml_service.db.repositories import (
    ModelRepository, JobRepository, TrainingJobRepository, AlertRepository, 
    DriftCheckRepository, PredictionLogRepository, EventRepository, ApiTokenRepository
)
from ml_service.db.models import PredictionLog, Event, Job
from ml_service.ml.model import MLModel
from ml_service.ml.validators import DataValidator
from ml_service.core.config import settings
from ml_service.core.request_source import (
    detect_request_source, get_client_ip, get_user_agent,
    parse_user_agent, get_user_system_info, calculate_data_size
)
from ml_service.db.migrations import recreate_database
from ml_service.core.priority_queue import PriorityQueue
from ml_service.core.scheduler import Scheduler
from ml_service.db.models import Model

router = APIRouter()

# Import uuid for user creation
import uuid
import hashlib


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
        job_repo.update_status(job_id, "running", stage="validating")
        if event_repo and event_id:
            event_repo.update_status(event_id, "running", stage="validating")
        
        # Validate data before training
        if not request.items or len(request.items) == 0:
            raise ValueError("Training data is empty. Please provide at least one item.")
        
        # Check if all required fields exist in the data
        sample_item = request.items[0]
        available_fields = set(sample_item.keys())
        
        # Check target field
        if request.target_field not in available_fields:
            raise ValueError(
                f"Target field '{request.target_field}' not found in data. "
                f"Available fields: {', '.join(sorted(available_fields))}"
            )
        
        # Auto-detect feature fields if not provided
        if request.feature_fields is None or len(request.feature_fields) == 0:
            # Use all fields except target_field as features
            feature_fields = [f for f in available_fields if f != request.target_field]
            if len(feature_fields) == 0:
                raise ValueError(
                    f"No feature fields available. Target field '{request.target_field}' is the only field in data. "
                    f"Please provide at least one additional field for features."
                )
            logger.info(f"Auto-detected feature fields: {feature_fields}")
            # Update request object to include auto-detected fields
            request.feature_fields = feature_fields
        else:
            # Validate provided feature fields
            missing_features = [f for f in request.feature_fields if f not in available_fields]
            if missing_features:
                raise ValueError(
                    f"Feature fields not found in data: {', '.join(missing_features)}. "
                    f"Available fields: {', '.join(sorted(available_fields))}"
                )
        
        # Update status to training
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
        
        # Parse hidden_layers if provided
        hidden_layers_tuple = None
        if request.hidden_layers:
            try:
                # Parse string like "512,256,128" or "(512, 256, 128)"
                hidden_layers_str = request.hidden_layers.strip()
                # Remove parentheses if present
                if hidden_layers_str.startswith('(') and hidden_layers_str.endswith(')'):
                    hidden_layers_str = hidden_layers_str[1:-1]
                # Split by comma and convert to integers
                hidden_layers_tuple = tuple(int(x.strip()) for x in hidden_layers_str.split(','))
                logger.info(f"Parsed hidden_layers: {hidden_layers_tuple}")
            except Exception as e:
                logger.warning(f"Failed to parse hidden_layers '{request.hidden_layers}': {e}. Using auto-detection.")
        
        # Train model
        metrics = model.train(
            items=request.items,
            target_field=request.target_field,
            feature_fields=request.feature_fields,
            validation_split=request.validation_split,
            use_gpu=request.use_gpu_if_available,
            hidden_layers=hidden_layers_tuple,
            max_iter=request.max_iter,
            learning_rate_init=request.learning_rate_init,
            alpha=request.alpha
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
    """
    Start training a new model (async).
    Access: Admin and system_admin only.
    """
    from ml_service.core.security import require_admin
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    try:
        job_id = str(uuid.uuid4())
        
        # Get request metadata
        source = detect_request_source(http_request)
        client_ip = get_client_ip(http_request)
        user_agent = get_user_agent(http_request)
        
        # Parse user agent for OS and device
        ua_info = parse_user_agent(user_agent)
        system_info = get_user_system_info(http_request)
        
        # Get user info from auth
        user_id = user.get("user_id") if user else None
        user_tier = user.get("tier", "user") if user else "user"
        
        # Auto-detect feature fields if not provided (for request payload)
        feature_fields_for_payload = request.feature_fields
        if feature_fields_for_payload is None or len(feature_fields_for_payload) == 0:
            if request.items and len(request.items) > 0:
                available_fields = set(request.items[0].keys())
                feature_fields_for_payload = [f for f in available_fields if f != request.target_field]
        
        # Calculate data size
        request_data = {
            "model_key": request.model_key,
            "version": request.version,
            "items": request.items,
            "feature_fields": feature_fields_for_payload or [],
            "target_field": request.target_field
        }
        data_size_bytes = calculate_data_size(request_data)
        
        # Create job with all metadata
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
            user_agent=user_agent,
            priority=5,  # Will be recalculated by priority queue
            user_tier=user_tier,
            data_size_bytes=data_size_bytes,
            progress_current=0,
            progress_total=100,
            model_version=request.version,
            request_payload=json.dumps(request_data),
            user_os=ua_info.get("os"),
            user_device=ua_info.get("device"),
            user_cpu_cores=system_info.get("cpu_cores"),
            user_ram_gb=system_info.get("ram_gb"),
            user_gpu=system_info.get("gpu"),
            user_id=user_id
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
        
        # Note: Background task will be handled by scheduler/worker pool
        # For now, still add to background tasks for backward compatibility
        background_tasks.add_task(process_training_job, job_id, request, event.event_id)
        
        return TrainingResponse(
            job_id=job_id,
            status="queued",
            model_key=request.model_key,
            version=request.version,
            estimated_time=0  # Will be calculated by scheduler
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
        job_id = str(uuid.uuid4())
        
        # Get request metadata
        source = detect_request_source(http_request)
        client_ip = get_client_ip(http_request)
        user_agent = get_user_agent(http_request)
        
        # Verify model exists
        model_repo = ModelRepository()
        model = model_repo.get(request.model_key, request.version)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Parse user agent for OS and device
        ua_info = parse_user_agent(user_agent)
        system_info = get_user_system_info(http_request)
        
        # Get user info from auth
        user_id = user.get("user_id") if user else None
        user_tier = user.get("tier", "user") if user else "user"
        
        # Calculate data size
        request_data = {
            "model_key": request.model_key,
            "version": request.version,
            "data": request.data
        }
        data_size_bytes = calculate_data_size(request_data)
        
        # Create job with all metadata
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
            user_agent=user_agent,
            priority=5,  # Will be recalculated by priority queue
            user_tier=user_tier,
            data_size_bytes=data_size_bytes,
            progress_current=0,
            progress_total=100,
            model_version=request.version or model.version,
            request_payload=json.dumps(request_data),
            user_os=ua_info.get("os"),
            user_device=ua_info.get("device"),
            user_cpu_cores=system_info.get("cpu_cores"),
            user_ram_gb=system_info.get("ram_gb"),
            user_gpu=system_info.get("gpu"),
            user_id=user_id
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
        
        # Note: Background task will be handled by scheduler/worker pool
        background_tasks.add_task(process_predict_job, job_id, request, event.event_id)
        
        return PredictionJobResponse(
            job_id=job_id,
            status="queued",
            model_key=request.model_key,
            version=request.version or model.version,
            estimated_time=0  # Will be calculated by scheduler
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting prediction job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start prediction job: {str(e)}"
        )


@router.post("/retrain")
async def retrain_model(
    request: RetrainingRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    user: dict = AuthDep
):
    """
    Start retraining a model (async).
    Access: Admin and system_admin only.
    """
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    from ml_service.api.models import RetrainingRequest
    
    try:
        job_id = str(uuid.uuid4())
        
        # Get request metadata
        source = detect_request_source(http_request)
        client_ip = get_client_ip(http_request)
        user_agent = get_user_agent(http_request)
        
        # Verify base model exists
        model_repo = ModelRepository()
        base_model = model_repo.get(request.model_key, request.base_version)
        if not base_model:
            raise HTTPException(status_code=404, detail="Base model not found")
        
        # Parse user agent for OS and device
        ua_info = parse_user_agent(user_agent)
        system_info = get_user_system_info(http_request)
        
        # Get user info from auth
        user_id = user.get("user_id") if user else None
        user_tier = user.get("tier", "user") if user else "user"
        
        # Calculate data size
        request_data = {
            "model_key": request.model_key,
            "base_version": request.base_version,
            "new_version": request.new_version,
            "data_mode": request.data_mode,
            "items": request.items,
            "feature_fields": request.feature_fields,
            "target_field": request.target_field
        }
        data_size_bytes = calculate_data_size(request_data)
        
        # Create job with all metadata
        job = Job(
            job_id=job_id,
            model_key=request.model_key,
            job_type="retrain",
            status="queued",
            stage="queued",
            source=source,
            dataset_size=len(request.items),
            created_at=datetime.now(),
            client_ip=client_ip,
            user_agent=user_agent,
            priority=5,  # Will be recalculated by priority queue
            user_tier=user_tier,
            data_size_bytes=data_size_bytes,
            progress_current=0,
            progress_total=100,
            model_version=request.new_version,
            request_payload=json.dumps(request_data),
            user_os=ua_info.get("os"),
            user_device=ua_info.get("device"),
            user_cpu_cores=system_info.get("cpu_cores"),
            user_ram_gb=system_info.get("ram_gb"),
            user_gpu=system_info.get("gpu"),
            user_id=user_id
        )
        
        job_repo = JobRepository()
        job_repo.create(job)
        
        # Log event
        event_repo = EventRepository()
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type="retrain",
            source=source,
            model_key=request.model_key,
            status="queued",
            stage="queued",
            input_data=json.dumps({
                "model_key": request.model_key,
                "base_version": request.base_version,
                "new_version": request.new_version,
                "data_mode": request.data_mode,
                "items_count": len(request.items)
            }),
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=datetime.now()
        )
        event_repo.create(event)
        
        # Note: Background task will be handled by scheduler/worker pool
        # For now, we'll create a placeholder retrain function
        # background_tasks.add_task(process_retrain_job, job_id, request, event.event_id)
        
        return {
            "job_id": job_id,
            "status": "queued",
            "model_key": request.model_key,
            "base_version": request.base_version,
            "new_version": request.new_version,
            "estimated_time": 0
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting retraining job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start retraining job: {str(e)}"
        )


@router.get("/jobs", response_model=JobsResponse)
async def get_jobs(
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    model_key: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = AuthDep
):
    """
    Get list of jobs.
    For user: only own jobs.
    For admin/system_admin: all jobs.
    """
    job_repo = JobRepository()
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    # Filter by user_id for regular users
    filter_user_id = user_id if user_tier == "user" else None
    
    jobs = job_repo.get_all(
        limit=limit,
        offset=offset,
        job_type=job_type,
        status=status,
        model_key=model_key,
        user_id=filter_user_id
    )
    
    job_infos = [
        JobInfo(
            job_id=job.job_id,
            model_key=job.model_key,
            job_type=job.job_type,
            status=job.status,
            stage=job.stage,
            created_at=job.created_at or datetime.now(),
            started_at=job.started_at,
            completed_at=job.completed_at,
            dataset_size=job.dataset_size,
            error_message=job.error_message
        )
        for job in jobs
    ]
    
    return JobsResponse(jobs=job_infos, total=len(job_infos))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = AuthDep):
    """
    Get job details by ID.
    For user: only own jobs.
    For admin/system_admin: all jobs.
    """
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    # Check access: user can only see own jobs
    if user_tier == "user" and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied. Can only view own jobs.")
    
    return {
        "job_id": job.job_id,
        "model_key": job.model_key,
        "job_type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "dataset_size": job.dataset_size,
        "metrics": json.loads(job.metrics) if job.metrics else None,
        "error_message": job.error_message
    }


@router.get("/predict/{job_id}", response_model=PredictionResultResponse)
async def get_predict_result(job_id: str, user: dict = AuthDep):
    """Get prediction job results"""
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.job_type != "predict":
        raise HTTPException(status_code=400, detail="Job is not a prediction job")
    
    # Check access: user can only see own jobs
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    if user_tier == "user" and job.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied. Can only view own jobs.")
    
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


@router.delete("/models/{model_key}")
async def delete_model(
    model_key: str,
    delete_artifacts: bool = False,
    user: dict = AuthDep
):
    """
    Delete model and all related data.
    Access: Admin and system_admin only.
    """
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    model_repo = ModelRepository()
    
    # Check if model exists
    model = model_repo.get(model_key)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Delete model and related data
    success = model_repo.delete(model_key, delete_artifacts=delete_artifacts)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete model")
    
    return {
        "status": "deleted",
        "model_key": model_key,
        "artifacts_deleted": delete_artifacts
    }




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


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_tracking(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for tracking specific job"""
    from ml_service.api.websocket import manager
    import asyncio
    
    # Verify job exists
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        await websocket.close(code=1008, reason="Job not found")
        return
    
    await manager.connect(websocket)
    
    try:
        # Send initial status
        job_dict = {
            "job_id": job.job_id,
            "model_key": job.model_key,
            "job_type": job.job_type,
            "status": job.status,
            "stage": job.stage,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "error_message": job.error_message
        }
        await manager.send_personal_message({
            "type": "job:status",
            "job_id": job_id,
            "status": job.status,
            "job": job_dict,
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # Poll for updates every 2 seconds
        while True:
            await asyncio.sleep(2)
            
            # Get fresh job data
            updated_job = job_repo.get(job_id)
            if not updated_job:
                await manager.send_personal_message({
                    "type": "job:final",
                    "job_id": job_id,
                    "status": "not_found",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                break
            
            # Send status update
            updated_job_dict = {
                "job_id": updated_job.job_id,
                "model_key": updated_job.model_key,
                "job_type": updated_job.job_type,
                "status": updated_job.status,
                "stage": updated_job.stage,
                "created_at": updated_job.created_at.isoformat() if updated_job.created_at else None,
                "started_at": updated_job.started_at.isoformat() if updated_job.started_at else None,
                "completed_at": updated_job.completed_at.isoformat() if updated_job.completed_at else None,
                "progress_current": updated_job.progress_current,
                "progress_total": updated_job.progress_total,
                "error_message": updated_job.error_message
            }
            await manager.send_personal_message({
                "type": "job:status",
                "job_id": job_id,
                "status": updated_job.status,
                "job": updated_job_dict,
                "timestamp": datetime.now().isoformat()
            }, websocket)
            
            # If job is completed, send final message and close
            if updated_job.status in ('completed', 'failed', 'cancelled'):
                await manager.send_personal_message({
                    "type": "job:final",
                    "job_id": job_id,
                    "status": updated_job.status,
                    "job": updated_job_dict,
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                break
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket job tracking error: {e}")
        manager.disconnect(websocket)


@router.get("/health")
async def health_check():
    """Health check endpoint (no auth required)"""
    return {
        "status": "healthy",
        "version": "0.9.1",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/events")
async def get_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    model_key: Optional[str] = None,
    client_ip: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = AuthDep
):
    """Get all events with optional filters"""
    event_repo = EventRepository()
    events = event_repo.get_all(
        limit=limit,
        offset=offset,
        event_type=event_type,
        source=source,
        status=status,
        model_key=model_key,
        client_ip=client_ip
    )
    
    # Return events as dicts with all fields
    event_dicts = []
    for event in events:
        event_dict = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
            "model_key": event.model_key,
            "status": event.status,
            "stage": event.stage,
            "input_data": json.loads(event.input_data) if event.input_data else None,
            "output_data": json.loads(event.output_data) if event.output_data else None,
            "user_agent": event.user_agent,
            "client_ip": event.client_ip,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "completed_at": event.completed_at.isoformat() if event.completed_at else None,
            "error_message": event.error_message,
            "duration_ms": event.duration_ms,
            "display_format": event.display_format,
            "data_size_bytes": event.data_size_bytes
        }
        event_dicts.append(event_dict)
    
    return {
        "events": event_dicts,
        "total": len(event_dicts),
        "limit": limit,
        "offset": offset
    }


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = AuthDep):
    """Get event details"""
    event_repo = EventRepository()
    event = event_repo.get(event_id)
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "source": event.source,
        "model_key": event.model_key,
        "status": event.status,
        "stage": event.stage,
        "input_data": json.loads(event.input_data) if event.input_data else None,
        "output_data": json.loads(event.output_data) if event.output_data else None,
        "user_agent": event.user_agent,
        "client_ip": event.client_ip,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "completed_at": event.completed_at.isoformat() if event.completed_at else None,
        "error_message": event.error_message,
        "duration_ms": event.duration_ms,
        "display_format": event.display_format,
        "data_size_bytes": event.data_size_bytes
    }


@router.put("/events/{event_id}/format")
async def update_event_format(
    event_id: str,
    format: str = None,
    user: dict = AuthDep
):
    """Update event display format"""
    from pydantic import BaseModel
    
    class FormatRequest(BaseModel):
        format: str
    
    # Get format from request body if not in query
    if format is None:
        # Would need to read from request body
        format = "table"  # Default
    
    if format not in ('table', 'list', 'card'):
        raise HTTPException(status_code=400, detail="Format must be 'table', 'list', or 'card'")
    
    event_repo = EventRepository()
    success = event_repo.update_display_format(event_id, format)
    
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = event_repo.get(event_id)
    return {
        "event_id": event.event_id,
        "display_format": event.display_format
    }


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


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: dict = AuthDep):
    """Get job status with queue position and estimated wait time"""
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert to dict with all fields
    job_dict = job_repo.to_dict(job)
    
    # Calculate queue position if queued
    queue_position = None
    estimated_wait_time = None
    
    if job.status == "queued":
        queued_jobs = job_repo.get_queued_jobs(model_key=job.model_key)
        # Sort by priority DESC, then created_at ASC
        queued_jobs.sort(key=lambda j: (-j.priority, j.created_at or datetime.min))
        
        for idx, queued_job in enumerate(queued_jobs, 1):
            if queued_job.job_id == job_id:
                queue_position = idx
                break
        
        # Estimate wait time: average time per job * position
        # Rough estimate: 1 minute per job
        if queue_position:
            estimated_wait_time = queue_position * 60  # seconds
    
    job_dict["queue_position"] = queue_position
    job_dict["estimated_wait_time"] = estimated_wait_time
    
    return job_dict


@router.get("/jobs")
async def list_jobs(
    model_key: Optional[str] = None,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = AuthDep
):
    """List jobs with filtering and pagination"""
    job_repo = JobRepository()
    jobs = job_repo.get_all(limit=limit, offset=offset, job_type=job_type, status=status, model_key=model_key)
    
    # Convert to dicts
    job_dicts = [job_repo.to_dict(job) for job in jobs]
    
    # Get total count for pagination
    total = len(job_dicts)  # Simplified, should query count separately for accuracy
    
    return {
        "jobs": job_dicts,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user: dict = AuthDep):
    """Cancel a job"""
    job_repo = JobRepository()
    job = job_repo.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if job can be cancelled
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    # Update job status
    job_repo.update_status(job_id, "cancelled", stage="cancelled")
    job.completed_at = datetime.now()
    
    # Return updated job
    return job_repo.to_dict(job)


# Priority Queue endpoints
priority_queue = PriorityQueue()

# Scheduler instance (initialized at module level)
scheduler = Scheduler(max_workers_per_pool=5)


@router.get("/queue/stats")
async def get_queue_stats(user: dict = AuthDep):
    """Get queue statistics"""
    stats = priority_queue.get_queue_stats()
    return stats


@router.get("/queue/next")
async def get_next_job(
    model_key: Optional[str] = None,
    user: dict = AuthDep
):
    """Get next job from queue (for scheduler/workers)"""
    job = priority_queue.get_next_job(model_key=model_key)
    
    if not job:
        return {"job": None}
    
    job_repo = JobRepository()
    return {"job": job_repo.to_dict(job)}


# Scheduler endpoints
@router.get("/scheduler/stats")
async def get_scheduler_stats(user: dict = AuthDep):
    """Get scheduler statistics"""
    global scheduler
    if not scheduler:
        return {
            "running": False,
            "error": "Scheduler not initialized"
        }
    return scheduler.get_stats()


@router.post("/scheduler/pause")
async def pause_scheduler(user: dict = AuthDep):
    """Pause scheduler"""
    global scheduler
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    scheduler.pause()
    return {"status": "paused", "running": scheduler.running}


@router.post("/scheduler/resume")
async def resume_scheduler(user: dict = AuthDep):
    """Resume scheduler"""
    global scheduler
    if not scheduler:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")
    scheduler.resume()
    return {"status": "resumed", "running": scheduler.running}


# Admin endpoints
@router.post("/admin/recreate-db")
async def recreate_db(
    backup: bool = True,
    restore_from_backup: bool = False,
    user: dict = AuthDep
):
    """
    Recreate database with clean schema.
    Access: Admin and system_admin only.
    
    WARNING: This will delete all data unless restore_from_backup is True!
    
    Args:
        backup: Create backup before deletion (default: True)
        restore_from_backup: Restore data from backup after recreation (default: False)
    """
    # Check admin rights
    user_tier = user.get("tier", "user") if user else "user"
    if user_tier not in ["system_admin", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin rights required."
        )
    
    result = recreate_database(backup=backup, restore_from_backup=restore_from_backup)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=f"Failed to recreate database: {result.get('error')}"
        )
    
    return result


# Authentication endpoints
@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with username and password.
    Returns authentication token.
    Access: Public (available to all users)
    """
    from ml_service.db.connection import db
    from ml_service.db.repositories import ApiTokenRepository
    from ml_service.db.models import ApiToken
    from ml_service.core.security import generate_token, hash_token
    from ml_service.core.config import settings
    
    # Hash the provided password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    # Check user credentials
    with db.get_connection() as conn:
        user_row = conn.execute("""
            SELECT user_id, username, tier, is_active
            FROM users
            WHERE username = ? AND password_hash = ? AND is_active = 1
        """, (request.username, password_hash)).fetchone()
        
        if not user_row:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )
        
        # Update last login
        conn.execute("""
            UPDATE users SET last_login = ? WHERE user_id = ?
        """, (datetime.now(), user_row['user_id']))
        
        # Generate secure token
        token = generate_token()
        token_hash = hash_token(token)
        
        # Calculate expiration date
        expires_at = datetime.now() + timedelta(days=settings.ML_SESSION_EXPIRY_DAYS)
        expires_in_seconds = int(settings.ML_SESSION_EXPIRY_DAYS * 24 * 60 * 60)
        
        # Save token in database
        token_repo = ApiTokenRepository()
        api_token = ApiToken(
            token_id=str(uuid.uuid4()),
            token_hash=token_hash,
            user_id=user_row['user_id'],
            token_type="session",
            name=None,
            created_at=datetime.now(),
            expires_at=expires_at,
            last_used_at=None,
            is_active=1
        )
        token_repo.create(api_token)
        
        return LoginResponse(
            token=token,
            user_id=user_row['user_id'],
            username=user_row['username'],
            tier=user_row['tier'] or 'user',
            expires_in=expires_in_seconds
        )


@router.get("/auth/user-info")
async def get_user_info(user: dict = AuthDep):
    """
    Get current user information based on token.
    Returns user tier and other info.
    """
    return {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "tier": user.get("tier"),
        "authenticated": user.get("authenticated", True)
    }


# Registration and user management endpoints
@router.post("/auth/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """
    Register a new user.
    Access: Public (available to all)
    """
    from ml_service.db.connection import db
    
    # Hash password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    # Check if username already exists
    with db.get_connection() as conn:
        existing_user = conn.execute("""
            SELECT user_id FROM users WHERE username = ?
        """, (request.username,)).fetchone()
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )
        
        # Create new user with tier="user"
        user_id = str(uuid.uuid4())
        created_at = datetime.now()
        
        conn.execute("""
            INSERT INTO users (user_id, username, password_hash, tier, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, request.username, password_hash, 'user', created_at, 1))
        
        return RegisterResponse(
            user_id=user_id,
            username=request.username,
            tier='user',
            created_at=created_at
        )


# User management endpoints (admin only)
@router.post("/auth/users", response_model=UserInfo)
async def create_user(request: CreateUserRequest, user: dict = AuthDep):
    """
    Create a new user (admin only).
    """
    from ml_service.core.security import require_admin, can_create_tier
    from ml_service.db.connection import db
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    
    # Check if can create this tier
    if not can_create_tier(user, request.tier):
        raise HTTPException(
            status_code=403,
            detail=f"You cannot create users with tier '{request.tier}'"
        )
    
    # Hash password
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    # Check if username already exists
    with db.get_connection() as conn:
        existing_user = conn.execute("""
            SELECT user_id FROM users WHERE username = ?
        """, (request.username,)).fetchone()
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )
        
        # Create new user
        user_id = str(uuid.uuid4())
        created_at = datetime.now()
        
        conn.execute("""
            INSERT INTO users (user_id, username, password_hash, tier, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, request.username, password_hash, request.tier, created_at, 1))
        
        return UserInfo(
            user_id=user_id,
            username=request.username,
            tier=request.tier,
            created_at=created_at,
            last_login=None,
            is_active=True
        )


@router.get("/auth/users", response_model=UsersResponse)
async def get_users(
    tier: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: dict = AuthDep
):
    """
    Get list of users (admin only).
    system_admin sees all users, admin sees only users with tier='user'.
    """
    from ml_service.db.connection import db
    from dateutil.parser import parse as parse_date
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    
    with db.get_connection() as conn:
        conditions = []
        params = []
        
        # Filter by tier for admin (can only see users)
        if user.get("tier") == "admin":
            conditions.append("tier = ?")
            params.append("user")
        # system_admin sees all
        
        if tier:
            conditions.append("tier = ?")
            params.append(tier)
        
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        rows = conn.execute(f"""
            SELECT * FROM users WHERE {where_clause} ORDER BY created_at DESC
        """, params).fetchall()
        
        users = [
            UserInfo(
                user_id=row['user_id'],
                username=row['username'],
                tier=row['tier'],
                created_at=parse_date(row['created_at']) if row['created_at'] else datetime.now(),
                last_login=parse_date(row['last_login']) if row['last_login'] else None,
                is_active=bool(row['is_active'])
            )
            for row in rows
        ]
        
        return UsersResponse(users=users, total=len(users))


@router.get("/auth/users/{user_id}", response_model=UserInfo)
async def get_user(user_id: str, user: dict = AuthDep):
    """
    Get user information (admin only).
    """
    from ml_service.core.security import can_manage_user
    from ml_service.db.connection import db
    from dateutil.parser import parse as parse_date
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    
    with db.get_connection() as conn:
        user_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if can manage this user
        if not can_manage_user(user, user_row['tier']):
            raise HTTPException(status_code=403, detail="Access denied. Cannot manage this user.")
        
        return UserInfo(
            user_id=user_row['user_id'],
            username=user_row['username'],
            tier=user_row['tier'],
            created_at=parse_date(user_row['created_at']) if user_row['created_at'] else datetime.now(),
            last_login=parse_date(user_row['last_login']) if user_row['last_login'] else None,
            is_active=bool(user_row['is_active'])
        )


@router.put("/auth/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: str,
    tier: Optional[str] = None,
    is_active: Optional[bool] = None,
    user: dict = AuthDep
):
    """
    Update user information (admin only).
    """
    from ml_service.core.security import can_manage_user, can_create_tier
    from ml_service.db.connection import db
    from dateutil.parser import parse as parse_date
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    
    with db.get_connection() as conn:
        # Get target user
        target_user_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not target_user_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if can manage this user
        if not can_manage_user(user, target_user_row['tier']):
            raise HTTPException(status_code=403, detail="Access denied. Cannot manage this user.")
        
        # Check tier change permissions
        if tier and tier != target_user_row['tier']:
            if tier == "system_admin":
                raise HTTPException(
                    status_code=403,
                    detail="Cannot change tier to system_admin. Only created from .env"
                )
            if not can_create_tier(user, tier):
                raise HTTPException(
                    status_code=403,
                    detail=f"You cannot change tier to '{tier}'"
                )
        
        # Update user
        updates = []
        params = []
        
        if tier is not None:
            updates.append("tier = ?")
            params.append(tier)
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if updates:
            params.append(user_id)
            conn.execute(f"""
                UPDATE users SET {', '.join(updates)} WHERE user_id = ?
            """, params)
        
        # Return updated user
        updated_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        return UserInfo(
            user_id=updated_row['user_id'],
            username=updated_row['username'],
            tier=updated_row['tier'],
            created_at=parse_date(updated_row['created_at']) if updated_row['created_at'] else datetime.now(),
            last_login=parse_date(updated_row['last_login']) if updated_row['last_login'] else None,
            is_active=bool(updated_row['is_active'])
        )


@router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str, user: dict = AuthDep):
    """
    Delete user (soft delete, admin only).
    """
    from ml_service.core.security import can_manage_user
    from ml_service.db.connection import db
    from ml_service.db.repositories import ApiTokenRepository
    
    # Check admin rights
    if user.get("tier") not in ["system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin rights required.")
    
    with db.get_connection() as conn:
        # Get target user
        target_user_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not target_user_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Cannot delete yourself
        if user.get("user_id") == user_id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
        # Check if can manage this user
        if not can_manage_user(user, target_user_row['tier']):
            raise HTTPException(status_code=403, detail="Access denied. Cannot manage this user.")
        
        # Check if last system_admin
        if target_user_row['tier'] == 'system_admin':
            active_system_admins = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE tier = 'system_admin' AND is_active = 1 AND user_id != ?
            """, (user_id,)).fetchone()
            
            if active_system_admins and active_system_admins['count'] == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the last system_admin"
                )
        
        # Soft delete user
        conn.execute("""
            UPDATE users SET is_active = 0 WHERE user_id = ?
        """, (user_id,))
        
        # Revoke all tokens
        token_repo = ApiTokenRepository()
        token_repo.revoke_all_tokens(user_id)
        
        return {"status": "success", "message": "User deleted successfully"}


# Profile endpoints
@router.get("/auth/profile", response_model=UserProfileResponse)
async def get_profile(user: dict = AuthDep):
    """
    Get current user profile.
    """
    from ml_service.db.connection import db
    from dateutil.parser import parse as parse_date
    
    user_id = user.get("user_id")
    
    with db.get_connection() as conn:
        user_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserProfileResponse(
            user_id=user_row['user_id'],
            username=user_row['username'],
            tier=user_row['tier'],
            created_at=parse_date(user_row['created_at']) if user_row['created_at'] else datetime.now(),
            last_login=parse_date(user_row['last_login']) if user_row['last_login'] else None
        )


@router.put("/auth/profile/password")
async def change_password(request: ChangePasswordRequest, user: dict = AuthDep):
    """
    Change user password.
    """
    from ml_service.db.connection import db
    from ml_service.db.repositories import ApiTokenRepository
    
    user_id = user.get("user_id")
    
    # Check current password
    password_hash = hashlib.sha256(request.current_password.encode()).hexdigest()
    
    with db.get_connection() as conn:
        user_row = conn.execute("""
            SELECT password_hash FROM users WHERE user_id = ? AND is_active = 1
        """, (user_id,)).fetchone()
        
        if not user_row or user_row['password_hash'] != password_hash:
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Update password
        new_password_hash = hashlib.sha256(request.new_password.encode()).hexdigest()
        conn.execute("""
            UPDATE users SET password_hash = ? WHERE user_id = ?
        """, (new_password_hash, user_id))
        
        # Revoke all sessions
        token_repo = ApiTokenRepository()
        token_repo.revoke_all_sessions(user_id)
        
        return {"status": "success", "message": "Password changed successfully"}


@router.put("/auth/profile/username", response_model=UserProfileResponse)
async def change_username(request: ChangeUsernameRequest, user: dict = AuthDep):
    """
    Change username.
    """
    from ml_service.db.connection import db
    from dateutil.parser import parse as parse_date
    
    user_id = user.get("user_id")
    
    # Check if new username is unique
    with db.get_connection() as conn:
        existing_user = conn.execute("""
            SELECT user_id FROM users WHERE username = ? AND user_id != ?
        """, (request.new_username, user_id)).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Update username
        conn.execute("""
            UPDATE users SET username = ? WHERE user_id = ?
        """, (request.new_username, user_id))
        
        # Return updated profile
        user_row = conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        return UserProfileResponse(
            user_id=user_row['user_id'],
            username=user_row['username'],
            tier=user_row['tier'],
            created_at=parse_date(user_row['created_at']) if user_row['created_at'] else datetime.now(),
            last_login=parse_date(user_row['last_login']) if user_row['last_login'] else None
        )


@router.delete("/auth/profile")
async def delete_profile(user: dict = AuthDep):
    """
    Delete current user account (soft delete).
    """
    from ml_service.db.connection import db
    from ml_service.db.repositories import ApiTokenRepository
    
    user_id = user.get("user_id")
    
    with db.get_connection() as conn:
        # Check if last system_admin
        user_row = conn.execute("""
            SELECT tier FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if user_row and user_row['tier'] == 'system_admin':
            active_system_admins = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE tier = 'system_admin' AND is_active = 1 AND user_id != ?
            """, (user_id,)).fetchone()
            
            if active_system_admins and active_system_admins['count'] == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the last system_admin"
                )
        
        # Soft delete user
        conn.execute("""
            UPDATE users SET is_active = 0 WHERE user_id = ?
        """, (user_id,))
        
        # Revoke all tokens
        token_repo = ApiTokenRepository()
        token_repo.revoke_all_tokens(user_id)
        
        return {"status": "success", "message": "Account deleted successfully"}


# API tokens endpoints
@router.post("/auth/tokens", response_model=TokenResponse)
async def create_token(request: CreateTokenRequest, user: dict = AuthDep):
    """
    Create API token for current user.
    """
    from ml_service.db.repositories import ApiTokenRepository
    from ml_service.db.models import ApiToken
    from ml_service.core.security import generate_token, hash_token
    from ml_service.core.config import settings
    from dateutil.parser import parse as parse_date
    
    user_id = user.get("user_id")
    user_tier = user.get("tier", "user")
    
    # Generate token
    token = generate_token()
    token_hash = hash_token(token)
    
    # Calculate expiration
    expires_at = datetime.now() + timedelta(days=settings.ML_TOKEN_EXPIRY_DAYS)
    
    # Create token in database
    token_repo = ApiTokenRepository()
    api_token = ApiToken(
        token_id=str(uuid.uuid4()),
        token_hash=token_hash,
        user_id=user_id,
        token_type="api",
        name=request.name,
        created_at=datetime.now(),
        expires_at=expires_at,
        last_used_at=None,
        is_active=1
    )
    token_repo.create(api_token)
    
    # Generate permissions description
    permissions = {
        "tier": user_tier,
        "allowed_endpoints": []
    }
    
    if user_tier == "user":
        permissions["allowed_endpoints"] = [
            "GET /health",
            "GET /jobs (own only)",
            "GET /models",
            "POST /predict"
        ]
        permissions["description"] = "Пользователь может просматривать свои задачи, использовать модели для предсказаний"
    elif user_tier in ["admin", "system_admin"]:
        permissions["allowed_endpoints"] = [
            "All endpoints available"
        ]
        permissions["description"] = "Полный доступ ко всем эндпоинтам"
    
    return TokenResponse(
        token=token,
        token_id=api_token.token_id,
        created_at=api_token.created_at,
        expires_at=api_token.expires_at,
        permissions=permissions
    )


@router.get("/auth/tokens", response_model=TokensResponse)
async def get_tokens(
    token_type: Optional[str] = None,
    user: dict = AuthDep
):
    """
    Get list of tokens for current user.
    For admin/system_admin: can see all tokens if requested.
    """
    from ml_service.db.repositories import ApiTokenRepository
    from dateutil.parser import parse as parse_date
    
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    token_repo = ApiTokenRepository()
    
    # For system_admin/admin, can see all tokens; for user only own
    if user_tier == "system_admin":
        tokens_list = token_repo.get_all(token_type=token_type)
    elif user_tier == "admin":
        # Admin can see tokens of users only
        all_tokens = token_repo.get_all(token_type=token_type)
        # Filter to show only user tokens
        tokens_list = [t for t in all_tokens if t.user_id != user_id]
        # Also add own tokens
        own_tokens = token_repo.get_by_user(user_id, token_type=token_type)
        tokens_list.extend(own_tokens)
    else:
        tokens_list = token_repo.get_by_user(user_id, token_type=token_type)
    
    return TokensResponse(
        tokens=[
            TokenInfo(
                token_id=t.token_id,
                name=t.name,
                token_type=t.token_type,
                created_at=t.created_at or datetime.now(),
                last_used_at=t.last_used_at,
                expires_at=t.expires_at,
                is_active=bool(t.is_active)
            )
            for t in tokens_list
        ]
    )


@router.post("/auth/tokens/{token_id}/revoke")
async def revoke_token(token_id: str, user: dict = AuthDep):
    """
    Revoke a token.
    """
    from ml_service.db.repositories import ApiTokenRepository
    
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    token_repo = ApiTokenRepository()
    
    # Get token
    all_tokens = token_repo.get_all()
    token = next((t for t in all_tokens if t.token_id == token_id), None)
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # Check permissions: user can only revoke own tokens
    if user_tier == "user" and token.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied. Cannot revoke other users' tokens")
    
    # Revoke token
    token_repo.revoke(token_id)
    
    return {"status": "success", "message": "Token revoked successfully"}


@router.delete("/auth/tokens/{token_id}")
async def delete_token(token_id: str, user: dict = AuthDep):
    """
    Delete a token.
    """
    from ml_service.db.repositories import ApiTokenRepository
    
    user_id = user.get("user_id")
    user_tier = user.get("tier")
    
    token_repo = ApiTokenRepository()
    
    # Get token
    all_tokens = token_repo.get_all()
    token = next((t for t in all_tokens if t.token_id == token_id), None)
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # Check permissions: user can only delete own tokens
    if user_tier == "user" and token.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied. Cannot delete other users' tokens")
    
    # Delete token
    token_repo.delete(token_id)
    
    return {"status": "success", "message": "Token deleted successfully"}


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
    jobs = job_repo.get_all(limit=10, model_key=model_key, job_type="train")
    
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


"""Pydantic models for API requests and responses"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# Training Request/Response
class TrainingRequest(BaseModel):
    model_key: str = Field(..., description="Unique model identifier")
    version: str = Field(..., description="Semantic version (e.g., v1.0.0)")
    task_type: str = Field(default="classification", description="Task type")
    target_field: str = Field(..., description="Target column name")
    feature_fields: List[str] = Field(..., description="Feature column names")
    dataset_name: str = Field(..., description="Dataset name")
    batch_size: str = Field(default="auto", description="Batch size")
    use_gpu_if_available: bool = Field(default=False, description="Use GPU if available")
    early_stopping: bool = Field(default=True, description="Enable early stopping")
    validation_split: float = Field(default=0.1, ge=0.0, le=1.0, description="Validation split")
    items: List[Dict[str, Any]] = Field(..., description="Training data")


class TrainingResponse(BaseModel):
    job_id: str
    status: str
    model_key: str
    version: str
    estimated_time: Optional[int] = None


# Prediction Request/Response
class PredictionRequest(BaseModel):
    model_key: str = Field(..., description="Model identifier")
    version: Optional[str] = Field(None, description="Model version (defaults to latest)")
    data: List[Dict[str, Any]] = Field(..., description="Input data for prediction")


class PredictionItem(BaseModel):
    input: Dict[str, Any]
    prediction: str
    confidence: float
    all_scores: Dict[str, float]


class PredictionResponse(BaseModel):
    predictions: List[PredictionItem]
    processing_time_ms: int
    unexpected_items: Optional[List[Dict[str, Any]]] = None


class PredictionJobResponse(BaseModel):
    """Response for async prediction job submission"""
    job_id: str
    status: str
    model_key: str
    version: Optional[str] = None
    estimated_time: Optional[int] = None


class PredictionResultResponse(BaseModel):
    """Response for getting prediction job results"""
    job_id: str
    status: str
    predictions: Optional[List[PredictionItem]] = None
    processing_time_ms: Optional[int] = None
    unexpected_items: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None


# Quality Check Request/Response
class QualityRequest(BaseModel):
    model_key: str
    version: Optional[str] = None


class QualityResponse(BaseModel):
    model_key: str
    version: str
    metrics: Dict[str, float]
    samples_analyzed: int
    last_updated: datetime


# Models List Response
class ModelInfo(BaseModel):
    model_key: str
    versions: List[str]
    active_version: str
    status: str
    accuracy: Optional[float] = None
    last_trained: Optional[datetime] = None


class ModelsResponse(BaseModel):
    models: List[ModelInfo]


# Alerts Response
class AlertInfo(BaseModel):
    alert_id: str
    type: str
    severity: str
    model_key: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    dismissible: bool = True


class AlertsResponse(BaseModel):
    alerts: List[AlertInfo]


# Drift Reports Response
class DriftReport(BaseModel):
    check_id: str
    model_key: str
    check_date: str
    psi_value: Optional[float] = None
    js_divergence: Optional[float] = None
    drift_detected: bool
    items_analyzed: Optional[int] = None
    created_at: datetime


class DriftReportsResponse(BaseModel):
    reports: List[DriftReport]


# Events Response
class EventInfo(BaseModel):
    event_id: str
    event_type: str  # drift, predict, train
    source: str  # api, gui, system
    model_key: Optional[str] = None
    status: str
    stage: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None
    client_ip: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class EventsResponse(BaseModel):
    events: List[EventInfo]


# Job Response (updated to support all job types)
class JobInfo(BaseModel):
    job_id: str
    model_key: str
    job_type: str  # train, predict, drift, other
    status: str
    stage: Optional[str] = None
    source: str  # api, gui, system
    dataset_size: Optional[int] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class JobsResponse(BaseModel):
    jobs: List[JobInfo]

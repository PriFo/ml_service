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
    feature_fields: Optional[List[str]] = Field(None, description="Feature column names (auto-detected if not provided)")
    dataset_name: str = Field(..., description="Dataset name")
    batch_size: str = Field(default="auto", description="Batch size")
    use_gpu_if_available: bool = Field(default=False, description="Use GPU if available")
    early_stopping: bool = Field(default=True, description="Enable early stopping")
    validation_split: float = Field(default=0.1, ge=0.0, le=1.0, description="Validation split")
    items: List[Dict[str, Any]] = Field(..., description="Training data")
    # Optional model parameters
    hidden_layers: Optional[str] = Field(None, description="Hidden layer sizes as comma-separated string (e.g., '512,256,128') or tuple string")
    max_iter: Optional[int] = Field(None, description="Maximum number of iterations")
    learning_rate_init: Optional[float] = Field(None, description="Initial learning rate")
    alpha: Optional[float] = Field(None, description="L2 regularization parameter")


class TrainingResponse(BaseModel):
    job_id: str
    status: str
    model_key: str
    version: str
    estimated_time: Optional[int] = None


# Retraining Request/Response
class RetrainingRequest(BaseModel):
    model_key: str = Field(..., description="Model identifier")
    base_version: str = Field(..., description="Base model version to retrain from")
    new_version: str = Field(..., description="New version for retrained model")
    data_mode: str = Field(default="replace", description="Data mode: 'replace' or 'append'")
    target_field: str = Field(..., description="Target column name")
    feature_fields: Optional[List[str]] = Field(None, description="Feature column names (auto-detected if not provided)")
    items: List[Dict[str, Any]] = Field(..., description="New training data")
    validation_split: float = Field(default=0.1, ge=0.0, le=1.0, description="Validation split")
    use_gpu_if_available: bool = Field(default=False, description="Use GPU if available")


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


# Authentication models
class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    token: str = Field(..., description="Authentication token")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    tier: str = Field(..., description="User tier (system_admin, admin, user)")
    expires_in: Optional[int] = Field(None, description="Token expiration time in seconds")


# Registration
class RegisterRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class RegisterResponse(BaseModel):
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    tier: str = Field(..., description="User tier")
    created_at: datetime = Field(..., description="Creation timestamp")


# User management
class CreateUserRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    tier: str = Field(..., description="User tier (user or admin)")


class UserInfo(BaseModel):
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    tier: str = Field(..., description="User tier")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_active: bool = Field(..., description="Is user active")


class UsersResponse(BaseModel):
    users: List[UserInfo] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")


# Profile management
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class ChangeUsernameRequest(BaseModel):
    new_username: str = Field(..., description="New username")


class UserProfileResponse(BaseModel):
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    tier: str = Field(..., description="User tier")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")


# API tokens
class CreateTokenRequest(BaseModel):
    name: Optional[str] = Field(None, description="Token name/description")


class TokenInfo(BaseModel):
    token_id: str = Field(..., description="Token ID")
    name: Optional[str] = Field(None, description="Token name")
    token_type: str = Field(..., description="Token type (session or api)")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    is_active: bool = Field(..., description="Is token active")


class TokenResponse(BaseModel):
    token: str = Field(..., description="Token (only returned once)")
    token_id: str = Field(..., description="Token ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    permissions: dict = Field(..., description="Permission description")


class TokensResponse(BaseModel):
    tokens: List[TokenInfo] = Field(..., description="List of tokens")

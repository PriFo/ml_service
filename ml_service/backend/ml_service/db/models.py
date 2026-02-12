"""SQLAlchemy models for database"""
from datetime import datetime, date
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json


@dataclass
class Model:
    """Model entity"""
    model_key: str
    version: str
    status: str = "active"  # active, archived
    accuracy: Optional[float] = None
    created_at: Optional[datetime] = None
    last_trained: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    task_type: Optional[str] = None
    target_field: Optional[str] = None
    feature_fields: Optional[str] = None  # JSON string


@dataclass
class Job:
    """Job entity (supports train, predict, drift, other)"""
    job_id: str
    model_key: str
    job_type: str = "train"  # train, predict, drift, other (alias: type)
    status: str = "queued"  # queued, running, completed, failed, cancelled
    stage: Optional[str] = None  # этап обработки
    source: str = "api"  # api, gui, system
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dataset_size: Optional[int] = None
    metrics: Optional[str] = None  # JSON string
    error_message: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    # New fields for v3.2
    priority: int = 5  # 0-14, calculated priority
    user_tier: str = "user"  # system_admin, admin, user
    user_id: Optional[str] = None  # User who created the job
    data_size_bytes: Optional[int] = None  # Size of dataset in bytes
    progress_current: int = 0  # Current progress
    progress_total: int = 100  # Total progress
    model_version: Optional[str] = None  # Model version
    assigned_worker_id: Optional[str] = None  # Worker handling this job
    request_payload: Optional[str] = None  # JSON string with original request data
    result_payload: Optional[str] = None  # JSON string with results
    user_os: Optional[str] = None  # Detected OS from user agent
    user_device: Optional[str] = None  # Detected device from user agent
    user_cpu_cores: Optional[int] = None  # User's CPU cores if available
    user_ram_gb: Optional[float] = None  # User's RAM in GB if available
    user_gpu: Optional[str] = None  # User's GPU info if available


# Backward compatibility alias
TrainingJob = Job


@dataclass
class ClientDataset:
    """Client dataset entity"""
    dataset_id: str
    model_key: str
    dataset_version: int
    created_at: Optional[datetime] = None
    item_count: Optional[int] = None
    confidence_threshold: float = 0.8
    status: str = "active"  # active, processing, archived


@dataclass
class RetrainingJob:
    """Retraining job entity"""
    job_id: str
    model_key: str
    source_model_version: str
    new_model_version: str
    old_metrics: Optional[str] = None  # JSON string
    new_metrics: Optional[str] = None  # JSON string
    accuracy_delta: Optional[float] = None
    status: str = "success"  # success, degradation_detected, failed
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reverted_at: Optional[datetime] = None


@dataclass
class DriftCheck:
    """Drift check entity"""
    check_id: str
    model_key: str
    check_date: date
    psi_value: Optional[float] = None
    js_divergence: Optional[float] = None
    drift_detected: bool = False
    items_analyzed: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Alert:
    """Alert entity"""
    alert_id: str
    type: str  # model_degradation, drift_detected
    severity: str = "info"  # info, warning, critical
    model_key: Optional[str] = None
    message: str = ""
    details: Optional[str] = None  # JSON string
    created_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None


@dataclass
class PredictionLog:
    """Prediction log entity for drift detection"""
    log_id: str
    model_key: str
    version: str
    input_features: Optional[bytes] = None  # Serialized input dataset (blob)
    prediction: Optional[bytes] = None  # Serialized prediction results (blob)
    confidence: Optional[float] = None  # Deprecated: no single confidence for batch predictions
    created_at: Optional[datetime] = None


@dataclass
class ApiToken:
    """API token entity (for sessions and API keys)"""
    token_id: str
    token_hash: str
    user_id: str
    token_type: str  # "session" or "api"
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: int = 1


@dataclass
class Event:
    """Event entity for monitoring all events (drift, predict, train)"""
    event_id: str
    event_type: str  # drift, predict, train
    source: str  # api, gui, system
    model_key: Optional[str] = None
    status: str = "queued"  # queued, running, completed, failed
    stage: Optional[str] = None  # этап обработки
    input_data: Optional[str] = None  # JSON string
    output_data: Optional[str] = None  # JSON string
    user_agent: Optional[str] = None
    client_ip: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    # New fields for v3.2
    duration_ms: Optional[int] = None  # Duration in milliseconds
    display_format: str = "table"  # table, list, card
    data_size_bytes: Optional[int] = None  # Size of data in bytes

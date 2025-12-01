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
    job_type: str = "train"  # train, predict, drift, other
    status: str = "queued"  # queued, running, completed, failed
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
    input_features: Optional[bytes] = None  # Serialized numpy array
    prediction: Optional[str] = None
    confidence: Optional[float] = None
    created_at: Optional[datetime] = None


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

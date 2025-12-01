"""Database tests"""
import pytest
from datetime import datetime

from ml_service.db.repositories import (
    ModelRepository, TrainingJobRepository, AlertRepository, DriftCheckRepository
)
from ml_service.db.models import Model, TrainingJob, Alert, DriftCheck


def test_model_repository_create_get(temp_db):
    """Test model repository create and get"""
    repo = ModelRepository()
    
    model = Model(
        model_key="test_model",
        version="v1.0.0",
        status="active",
        accuracy=0.95,
        created_at=datetime.now()
    )
    
    repo.create(model)
    
    retrieved = repo.get("test_model", "v1.0.0")
    assert retrieved is not None
    assert retrieved.model_key == "test_model"
    assert retrieved.version == "v1.0.0"
    assert retrieved.accuracy == 0.95


def test_training_job_repository(temp_db):
    """Test training job repository"""
    repo = TrainingJobRepository()
    
    job = TrainingJob(
        job_id="test_job_123",
        model_key="test_model",
        status="queued",
        created_at=datetime.now()
    )
    
    repo.create(job)
    
    retrieved = repo.get("test_job_123")
    assert retrieved is not None
    assert retrieved.job_id == "test_job_123"
    assert retrieved.status == "queued"
    
    # Update status
    repo.update_status("test_job_123", "running")
    updated = repo.get("test_job_123")
    assert updated.status == "running"
    assert updated.started_at is not None


def test_alert_repository(temp_db):
    """Test alert repository"""
    repo = AlertRepository()
    
    alert = Alert(
        alert_id="alert_123",
        type="model_degradation",
        severity="warning",
        model_key="test_model",
        message="Test alert",
        created_at=datetime.now()
    )
    
    repo.create(alert)
    
    active = repo.get_active()
    assert len(active) == 1
    assert active[0].alert_id == "alert_123"
    
    # Dismiss alert
    repo.dismiss("alert_123")
    active = repo.get_active()
    assert len(active) == 0


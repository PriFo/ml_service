"""Pytest configuration and fixtures"""
import pytest
import tempfile
import os
from pathlib import Path

from ml_service.db.connection import DatabaseConnection
from ml_service.db.migrations import create_schema


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Create database with schema
    db = DatabaseConnection(db_path=db_path)
    create_schema()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_training_data():
    """Sample training data"""
    return [
        {"name": "Product A", "description": "Test product", "label": "Product"},
        {"name": "Service B", "description": "Test service", "label": "Service"},
        {"name": "Product C", "description": "Another product", "label": "Product"},
    ]


@pytest.fixture
def sample_model_config():
    """Sample model configuration"""
    return {
        "model_key": "test_model",
        "version": "v1.0.0",
        "feature_fields": ["name", "description"],
        "target_field": "label"
    }


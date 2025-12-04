"""Pytest configuration and fixtures"""
import pytest
import tempfile
import os
from pathlib import Path

from ml_service.db.connection import db_manager
from ml_service.db.migrations import create_schemas_for_separated_databases
from ml_service.core.config import settings


@pytest.fixture
def temp_db():
    """Create temporary separated databases for testing"""
    # Create temporary directories for test databases
    temp_dir = tempfile.mkdtemp()
    
    models_path = os.path.join(temp_dir, "models.db")
    users_path = os.path.join(temp_dir, "users.db")
    logs_path = os.path.join(temp_dir, "logs.db")
    
    # Create test database manager with temporary paths
    from ml_service.db.connection import ModelsDatabase, UsersDatabase, LogsDatabase, DatabaseManager
    
    # Create test databases
    test_models_db = ModelsDatabase()
    test_models_db.db_path = models_path
    test_models_db._ensure_db_directory()
    
    test_users_db = UsersDatabase()
    test_users_db.db_path = users_path
    test_users_db._ensure_db_directory()
    
    test_logs_db = LogsDatabase()
    test_logs_db.db_path = logs_path
    test_logs_db._ensure_db_directory()
    
    # Create test database manager
    test_db_manager = DatabaseManager()
    test_db_manager.models_db = test_models_db
    test_db_manager.users_db = test_users_db
    test_db_manager.logs_db = test_logs_db
    
    # Temporarily override global db_manager
    from ml_service.db import connection
    original_db_manager = connection.db_manager
    connection.db_manager = test_db_manager
    
    # Also override in repositories
    from ml_service.db import repositories
    original_repo_db_manager = repositories.db_manager
    repositories.db_manager = test_db_manager
    
    # Create schemas for separated databases
    try:
        # Use test database manager for schema creation
        from ml_service.db.migrations import create_schemas_for_separated_databases
        # Temporarily override db_manager in migrations
        from ml_service.db import migrations
        original_migrations_db_manager = migrations.db_manager
        migrations.db_manager = test_db_manager
        create_schemas_for_separated_databases()
        migrations.db_manager = original_migrations_db_manager
    except Exception as e:
        # If schemas already exist, that's fine
        pass
    
    yield {
        "models": models_path,
        "users": users_path,
        "logs": logs_path,
        "temp_dir": temp_dir,
        "db_manager": test_db_manager
    }
    
    # Restore original db_manager
    connection.db_manager = original_db_manager
    repositories.db_manager = original_repo_db_manager
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


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


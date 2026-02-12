"""Database migrations"""
import os
import shutil
import logging
import uuid
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from ml_service.db.connection import db_manager
from ml_service.core.config import settings

logger = logging.getLogger(__name__)


def create_schema():
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() instead.
    """
    logger.warning("create_schema() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return


def migrate_v3_2_fields():
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() instead.
    """
    logger.warning("migrate_v3_2_fields() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return


def recreate_database(backup: bool = True, restore_from_backup: bool = False) -> dict:
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() to recreate separated databases.
    
    Args:
        backup: If True, create backup of current database before deletion
        restore_from_backup: If True, restore data from backup after recreation
    
    Returns:
        dict with status and backup path if created
    """
    logger.warning("recreate_database() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return {
        "status": "error",
        "error": "Legacy database support has been removed. Use create_schemas_for_separated_databases() instead."
    }


def migrate_v3_2_fields():
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() instead.
    """
    logger.warning("migrate_v3_2_fields() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return


def recreate_database(backup: bool = True, restore_from_backup: bool = False) -> dict:
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() to recreate separated databases.
    
    Args:
        backup: If True, create backup of current database before deletion
        restore_from_backup: If True, restore data from backup after recreation
    
    Returns:
        dict with status and backup path if created
    """
    logger.warning("recreate_database() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return {
        "status": "error",
        "error": "Legacy database support has been removed. Use create_schemas_for_separated_databases() instead."
    }


def run_migrations():
    """
    DEPRECATED: This function is no longer supported.
    Use create_schemas_for_separated_databases() instead.
    """
    logger.warning("run_migrations() is deprecated and no longer supported. Use create_schemas_for_separated_databases() instead.")
    return


def create_schemas_for_separated_databases():
    """Create schemas for separated databases (models, users, logs)"""
    logger.info("Creating schemas for separated databases...")
    
    # Create models database schema
    with db_manager.models_db.get_connection() as conn:
        # Models table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_key TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                accuracy REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_trained DATETIME,
                last_updated DATETIME,
                task_type TEXT,
                target_field TEXT,
                feature_fields TEXT,
                PRIMARY KEY (model_key, version)
            )
        """)
        
        # Jobs table (no FOREIGN KEY to models - different DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                job_type TEXT NOT NULL DEFAULT 'train',
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT,
                source TEXT DEFAULT 'api',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                started_at DATETIME,
                completed_at DATETIME,
                dataset_size INTEGER,
                metrics TEXT,
                error_message TEXT,
                client_ip TEXT,
                user_agent TEXT,
                priority INTEGER DEFAULT 5,
                user_tier TEXT DEFAULT 'user',
                user_id TEXT,
                data_size_bytes INTEGER,
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 100,
                model_version TEXT,
                assigned_worker_id TEXT,
                request_payload TEXT,
                result_payload TEXT,
                user_os TEXT,
                user_device TEXT,
                user_cpu_cores INTEGER,
                user_ram_gb REAL,
                user_gpu TEXT
            )
        """)
        
        # Client datasets table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS client_datasets (
                dataset_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                dataset_version INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                item_count INTEGER,
                confidence_threshold REAL DEFAULT 0.8,
                status TEXT DEFAULT 'active',
                UNIQUE(model_key, dataset_version)
            )
        """)
        
        # Retraining jobs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retraining_jobs (
                job_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                source_model_version TEXT NOT NULL,
                new_model_version TEXT NOT NULL,
                old_metrics TEXT,
                new_metrics TEXT,
                accuracy_delta REAL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                reverted_at DATETIME
            )
        """)
        
        # Drift checks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drift_checks (
                check_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                check_date DATE NOT NULL,
                psi_value REAL,
                js_divergence REAL,
                drift_detected BOOLEAN DEFAULT 0,
                items_analyzed INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(model_key, check_date)
            )
        """)
        
        # Alerts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                model_key TEXT,
                message TEXT NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                dismissed_at DATETIME,
                dismissed_by TEXT
            )
        """)
        
        # Prediction logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prediction_logs (
                log_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                version TEXT NOT NULL,
                input_features BLOB,
                prediction BLOB,
                confidence REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_logs_model_created ON prediction_logs(model_key, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority_created ON jobs(priority, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_model_key ON jobs(model_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)")
        
        conn.commit()
        logger.info("Models database schema created")
    
    # Create users database schema
    with db_manager.users_db.get_connection() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # API tokens table (no FOREIGN KEY - same DB but simplified)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                token_type TEXT NOT NULL,
                name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                last_used_at DATETIME,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id, token_type)")
        
        # Create system_admin if users table is empty
        existing_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        if existing_users and existing_users['count'] == 0:
            admin_username = settings.ML_ADMIN_USERNAME
            admin_password = settings.ML_ADMIN_PASSWORD
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            conn.execute("""
                INSERT INTO users (user_id, username, password_hash, tier)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), admin_username, password_hash, 'system_admin'))
            logger.info(f"Created system_admin user ({admin_username})")
        
        conn.commit()
        logger.info("Users database schema created")
    
    # Create logs database schema with separated event tables
    with db_manager.logs_db.get_connection() as conn:
        # Alert events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_events (
                event_id TEXT PRIMARY KEY,
                alert_id TEXT,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                model_key TEXT,
                message TEXT NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                client_ip TEXT,
                user_agent TEXT
            )
        """)
        
        # Train events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS train_events (
                event_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                version TEXT,
                job_id TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT,
                metrics TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                duration_ms INTEGER,
                data_size_bytes INTEGER
            )
        """)
        
        # Predict events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predict_events (
                event_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                version TEXT,
                job_id TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT,
                input_size INTEGER,
                output_size INTEGER,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                duration_ms INTEGER,
                data_size_bytes INTEGER,
                client_ip TEXT,
                user_agent TEXT
            )
        """)
        
        # Login events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_events (
                event_id TEXT PRIMARY KEY,
                user_id TEXT,
                username TEXT,
                event_type TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # System events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                component TEXT,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Drift events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drift_events (
                event_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                check_id TEXT,
                drift_detected INTEGER DEFAULT 0,
                psi_value REAL,
                js_divergence REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Job events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                model_key TEXT,
                status TEXT NOT NULL,
                stage TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                error_message TEXT
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_events_created ON alert_events(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_train_events_model ON train_events(model_key, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predict_events_model ON predict_events(model_key, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_events_user ON login_events(user_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_events_ip ON login_events(ip_address)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_model ON drift_events(model_key, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, created_at)")
        
        # Migration: Add stage column to predict_events if it doesn't exist
        try:
            cursor = conn.execute("PRAGMA table_info(predict_events)")
            columns = [row[1] for row in cursor.fetchall()]
            if "stage" not in columns:
                conn.execute("ALTER TABLE predict_events ADD COLUMN stage TEXT")
                logger.info("Added stage column to predict_events table")
        except Exception as e:
            logger.warning(f"Could not add stage column to predict_events: {e}")
        
        # Migration: Add output_data column to predict_events if it doesn't exist
        try:
            cursor = conn.execute("PRAGMA table_info(predict_events)")
            columns = [row[1] for row in cursor.fetchall()]
            if "output_data" not in columns:
                conn.execute("ALTER TABLE predict_events ADD COLUMN output_data TEXT")
                logger.info("Added output_data column to predict_events table")
        except Exception as e:
            logger.warning(f"Could not add output_data column to predict_events: {e}")
        
        # Migration: Add input_data column to predict_events if it doesn't exist
        try:
            cursor = conn.execute("PRAGMA table_info(predict_events)")
            columns = [row[1] for row in cursor.fetchall()]
            if "input_data" not in columns:
                conn.execute("ALTER TABLE predict_events ADD COLUMN input_data TEXT")
                logger.info("Added input_data column to predict_events table")
        except Exception as e:
            logger.warning(f"Could not add input_data column to predict_events: {e}")
        
        conn.commit()
        logger.info("Logs database schema created")
    
    logger.info("All separated database schemas created successfully")


def migrate_to_separated_databases() -> dict:
    """
    Migrate data from legacy single database to separated databases.
    
    Returns:
        dict with migration status
    """
    # Legacy database support has been removed
    logger.warning("migrate_to_separated_databases() is deprecated. Legacy database support has been removed.")
    return {
        "status": "skipped",
        "reason": "Legacy database support has been removed"
    }


def migrate_models_by_task_type() -> dict:
    """
    Migrate existing model files to new structure organized by task_type.
    Moves models from ML_MODELS_PATH/model_key/version to ML_MODELS_PATH/task_type/model_key/version
    
    Returns:
        dict with migration status and statistics
    """
    from ml_service.db.repositories import ModelRepository
    
    logger.info("Starting migration of model files by task_type...")
    
    model_repo = ModelRepository()
    models = model_repo.get_all()
    
    stats = {
        "total": len(models),
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }
    
    for model in models:
        try:
            task_type = model.task_type or "unknown"
            task_type_normalized = task_type.lower()
            
            # Skip if task_type is unknown (will be handled by backward compatibility)
            if task_type_normalized == "unknown":
                stats["skipped"] += 1
                stats["details"].append({
                    "model_key": model.model_key,
                    "version": model.version,
                    "status": "skipped",
                    "reason": "task_type is unknown"
                })
                continue
            
            # Define paths
            old_model_path = Path(settings.ML_MODELS_PATH) / model.model_key / model.version
            new_model_path = Path(settings.ML_MODELS_PATH) / task_type_normalized / model.model_key / model.version
            
            old_model_file = old_model_path / "model.joblib"
            new_model_file = new_model_path / "model.joblib"
            
            # Check if old file exists
            if not old_model_file.exists():
                stats["skipped"] += 1
                stats["details"].append({
                    "model_key": model.model_key,
                    "version": model.version,
                    "status": "skipped",
                    "reason": "model file not found in old location"
                })
                continue
            
            # Check if already migrated
            if new_model_file.exists():
                stats["skipped"] += 1
                stats["details"].append({
                    "model_key": model.model_key,
                    "version": model.version,
                    "status": "skipped",
                    "reason": "already in new location"
                })
                continue
            
            # Create new directory
            new_model_path.mkdir(parents=True, exist_ok=True)
            
            # Move model file
            shutil.move(str(old_model_file), str(new_model_file))
            logger.info(f"Migrated model file: {model.model_key} v{model.version} -> {task_type_normalized}/")
            
            # Migrate features
            old_features_path = Path(settings.ML_FEATURES_PATH) / model.model_key / model.version
            new_features_path = Path(settings.ML_FEATURES_PATH) / task_type_normalized / model.model_key / model.version
            
            if old_features_path.exists():
                new_features_path.mkdir(parents=True, exist_ok=True)
                # Move all feature files
                for feature_file in old_features_path.glob("*"):
                    if feature_file.is_file():
                        shutil.move(str(feature_file), str(new_features_path / feature_file.name))
                # Remove old directory if empty
                try:
                    old_features_path.rmdir()
                except:
                    pass
                logger.info(f"Migrated features: {model.model_key} v{model.version}")
            
            # Migrate baselines
            old_baselines_path = Path(settings.ML_BASELINES_PATH) / model.model_key / model.version
            new_baselines_path = Path(settings.ML_BASELINES_PATH) / task_type_normalized / model.model_key / model.version
            
            if old_baselines_path.exists():
                new_baselines_path.mkdir(parents=True, exist_ok=True)
                # Move all baseline files
                for baseline_file in old_baselines_path.glob("*"):
                    if baseline_file.is_file():
                        shutil.move(str(baseline_file), str(new_baselines_path / baseline_file.name))
                # Remove old directory if empty
                try:
                    old_baselines_path.rmdir()
                except:
                    pass
                logger.info(f"Migrated baselines: {model.model_key} v{model.version}")
            
            # Remove old model directory if empty
            try:
                old_model_path.rmdir()
                # Try to remove parent directory if empty
                old_model_key_path = old_model_path.parent
                if old_model_key_path.exists() and not any(old_model_key_path.iterdir()):
                    old_model_key_path.rmdir()
            except:
                pass
            
            stats["migrated"] += 1
            stats["details"].append({
                "model_key": model.model_key,
                "version": model.version,
                "task_type": task_type,
                "status": "migrated"
            })
            
        except Exception as e:
            logger.error(f"Error migrating model {model.model_key} v{model.version}: {e}", exc_info=True)
            stats["errors"] += 1
            stats["details"].append({
                "model_key": model.model_key,
                "version": model.version,
                "status": "error",
                "error": str(e)
            })
    
    logger.info(f"Model migration completed: {stats['migrated']} migrated, {stats['skipped']} skipped, {stats['errors']} errors")
    
    return {
        "status": "success" if stats["errors"] == 0 else "partial",
            "statistics": stats
        }


"""Database repositories for CRUD operations"""
import json
import uuid
import logging
import time
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Optional
from dateutil.parser import parse as parse_date

from ml_service.db.connection import db_manager
from ml_service.db.queue_manager import WriteOperation

logger = logging.getLogger(__name__)
from ml_service.db.models import (
    Model, Job, TrainingJob, ClientDataset, RetrainingJob, DriftCheck, Alert, PredictionLog, Event, ApiToken
)


def _queue_write(db_name: str, operation: WriteOperation, table: str, sql: str, params: tuple):
    """Helper function to queue write operations"""
    db = getattr(db_manager, f"{db_name}_db", None)
    if db:
        success = db.queue_write(operation, table, {"sql": sql, "params": params})
        if not success:
            # Queue is full - log warning but don't block
            logger.warning(f"Failed to queue write operation for {db_name}.{table} - queue is full. Operation will be retried later.")
            # Optionally: retry with exponential backoff or use synchronous write for critical operations
    else:
        logger.error(f"Database {db_name} not found")


class ModelRepository:
    """Repository for models"""
    
    def create(self, model: Model) -> Model:
        """Create a new model or update if exists (same model_key and version)"""
        # Check if model exists (read operation - direct access)
        with db_manager.models_db.get_connection() as conn:
            existing = conn.execute("""
                SELECT * FROM models WHERE model_key = ? AND version = ?
            """, (model.model_key, model.version)).fetchone()
        
        if existing:
            # Update existing model (queue write)
            sql = """
                UPDATE models SET
                    status = ?, accuracy = ?, last_trained = ?, last_updated = ?,
                    task_type = ?, target_field = ?, feature_fields = ?
                WHERE model_key = ? AND version = ?
            """
            params = (
                model.status, model.accuracy,
                model.last_trained or datetime.now(),
                datetime.now(),
                model.task_type, model.target_field, model.feature_fields,
                model.model_key, model.version
            )
            _queue_write("models", WriteOperation.UPDATE, "models", sql, params)
            logger.info(f"Queued update for model {model.model_key} v{model.version}")
        else:
            # Create new model (queue write)
            sql = """
                INSERT INTO models (
                    model_key, version, status, accuracy, created_at,
                    last_trained, last_updated, task_type, target_field, feature_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                model.model_key, model.version, model.status, model.accuracy,
                model.created_at or datetime.now(),
                model.last_trained, datetime.now(),
                model.task_type, model.target_field, model.feature_fields
            )
            _queue_write("models", WriteOperation.CREATE, "models", sql, params)
            logger.info(f"Queued create for model {model.model_key} v{model.version}")
        return model
    
    def get(self, model_key: str, version: Optional[str] = None) -> Optional[Model]:
        """Get a model by key and optionally version"""
        with db_manager.models_db.get_connection() as conn:
            if version:
                row = conn.execute("""
                    SELECT * FROM models WHERE model_key = ? AND version = ?
                """, (model_key, version)).fetchone()
            else:
                # Get latest version
                row = conn.execute("""
                    SELECT * FROM models 
                    WHERE model_key = ? 
                    ORDER BY last_trained DESC 
                    LIMIT 1
                """, (model_key,)).fetchone()
            
            if row:
                return Model(
                    model_key=row['model_key'],
                    version=row['version'],
                    status=row['status'],
                    accuracy=row['accuracy'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    last_trained=parse_date(row['last_trained']) if row['last_trained'] else None,
                    last_updated=parse_date(row['last_updated']) if row['last_updated'] else None,
                    task_type=row['task_type'],
                    target_field=row['target_field'],
                    feature_fields=row['feature_fields']
                )
            return None
    
    def get_all(self) -> List[Model]:
        """Get all models"""
        with db_manager.models_db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM models ORDER BY last_trained DESC").fetchall()
            return [
                Model(
                    model_key=row['model_key'],
                    version=row['version'],
                    status=row['status'],
                    accuracy=row['accuracy'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    last_trained=parse_date(row['last_trained']) if row['last_trained'] else None,
                    last_updated=parse_date(row['last_updated']) if row['last_updated'] else None,
                    task_type=row['task_type'],
                    target_field=row['target_field'],
                    feature_fields=row['feature_fields']
                )
                for row in rows
            ]
    
    def get_active_models(self) -> List[Model]:
        """Get all active models"""
        with db_manager.models_db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM models 
                WHERE status = 'active' 
                ORDER BY last_trained DESC
            """).fetchall()
            return [
                Model(
                    model_key=row['model_key'],
                    version=row['version'],
                    status=row['status'],
                    accuracy=row['accuracy'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    last_trained=parse_date(row['last_trained']) if row['last_trained'] else None,
                    last_updated=parse_date(row['last_updated']) if row['last_updated'] else None,
                    task_type=row['task_type'],
                    target_field=row['target_field'],
                    feature_fields=row['feature_fields']
                )
                for row in rows
            ]
    
    def update(self, model_key: str, **kwargs) -> bool:
        """Update model fields"""
        if not kwargs:
            return False
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        kwargs["last_updated"] = datetime.now()
        set_clause += ", last_updated = ?"
        
        sql = f"UPDATE models SET {set_clause} WHERE model_key = ?"
        params = tuple(list(kwargs.values()) + [model_key])
        _queue_write("models", WriteOperation.UPDATE, "models", sql, params)
        return True
    
    def delete(self, model_key: str, version: Optional[str] = None, delete_artifacts: bool = True) -> bool:
        """Delete model from database and all associated files (model, features, baselines)"""
        import shutil
        from pathlib import Path
        from ml_service.core.config import settings
        
        try:
            # Get model to find task_type
            model = self.get(model_key, version)
            if not model:
                logger.warning(f"Model {model_key} v{version or 'latest'} not found for deletion")
                return False
            
            task_type = model.task_type or "unknown"
            task_type_normalized = task_type.lower() if task_type else "unknown"
            
            # Delete from database
            with db_manager.models_db.get_connection() as conn:
                if version:
                    sql = "DELETE FROM models WHERE model_key = ? AND version = ?"
                    params = (model_key, version)
                else:
                    # Delete all versions
                    sql = "DELETE FROM models WHERE model_key = ?"
                    params = (model_key,)
                
                _queue_write("models", WriteOperation.DELETE, "models", sql, params)
                logger.info(f"Queued deletion of model {model_key} v{version or 'all versions'}")
            
            if delete_artifacts:
                # Delete model files
                if version:
                    # Delete specific version
                    model_path = Path(settings.ML_MODELS_PATH) / task_type_normalized / model_key / version
                    old_model_path = Path(settings.ML_MODELS_PATH) / model_key / version  # Old path for backward compatibility
                    
                    if model_path.exists():
                        shutil.rmtree(model_path, ignore_errors=True)
                        logger.info(f"Deleted model files: {model_path}")
                    if old_model_path.exists():
                        shutil.rmtree(old_model_path, ignore_errors=True)
                        logger.info(f"Deleted old model files: {old_model_path}")
                else:
                    # Delete all versions
                    model_path = Path(settings.ML_MODELS_PATH) / task_type_normalized / model_key
                    old_model_path = Path(settings.ML_MODELS_PATH) / model_key  # Old path
                    
                    if model_path.exists():
                        shutil.rmtree(model_path, ignore_errors=True)
                        logger.info(f"Deleted model directory: {model_path}")
                    if old_model_path.exists():
                        shutil.rmtree(old_model_path, ignore_errors=True)
                        logger.info(f"Deleted old model directory: {old_model_path}")
                
                # Delete features files
                if version:
                    features_path = Path(settings.ML_FEATURES_PATH) / task_type_normalized / model_key / version
                    old_features_path = Path(settings.ML_FEATURES_PATH) / model_key / version
                    
                    if features_path.exists():
                        shutil.rmtree(features_path, ignore_errors=True)
                        logger.info(f"Deleted features: {features_path}")
                    if old_features_path.exists():
                        shutil.rmtree(old_features_path, ignore_errors=True)
                        logger.info(f"Deleted old features: {old_features_path}")
                else:
                    features_path = Path(settings.ML_FEATURES_PATH) / task_type_normalized / model_key
                    old_features_path = Path(settings.ML_FEATURES_PATH) / model_key
                    
                    if features_path.exists():
                        shutil.rmtree(features_path, ignore_errors=True)
                        logger.info(f"Deleted features directory: {features_path}")
                    if old_features_path.exists():
                        shutil.rmtree(old_features_path, ignore_errors=True)
                        logger.info(f"Deleted old features directory: {old_features_path}")
                
                # Delete baselines files
                if version:
                    baselines_path = Path(settings.ML_BASELINES_PATH) / task_type_normalized / model_key / version
                    old_baselines_path = Path(settings.ML_BASELINES_PATH) / model_key / version
                    
                    if baselines_path.exists():
                        shutil.rmtree(baselines_path, ignore_errors=True)
                        logger.info(f"Deleted baselines: {baselines_path}")
                    if old_baselines_path.exists():
                        shutil.rmtree(old_baselines_path, ignore_errors=True)
                        logger.info(f"Deleted old baselines: {old_baselines_path}")
                else:
                    baselines_path = Path(settings.ML_BASELINES_PATH) / task_type_normalized / model_key
                    old_baselines_path = Path(settings.ML_BASELINES_PATH) / model_key
                    
                    if baselines_path.exists():
                        shutil.rmtree(baselines_path, ignore_errors=True)
                        logger.info(f"Deleted baselines directory: {baselines_path}")
                    if old_baselines_path.exists():
                        shutil.rmtree(old_baselines_path, ignore_errors=True)
                        logger.info(f"Deleted old baselines directory: {old_baselines_path}")
            
            # Also delete related jobs, datasets, etc.
            # Delete jobs
            job_sql = "DELETE FROM jobs WHERE model_key = ?"
            job_params = (model_key,)
            _queue_write("models", WriteOperation.DELETE, "jobs", job_sql, job_params)
            
            # Delete client datasets
            dataset_sql = "DELETE FROM client_datasets WHERE model_key = ?"
            dataset_params = (model_key,)
            _queue_write("models", WriteOperation.DELETE, "client_datasets", dataset_sql, dataset_params)
            
            # Delete drift checks
            drift_sql = "DELETE FROM drift_checks WHERE model_key = ?"
            drift_params = (model_key,)
            _queue_write("models", WriteOperation.DELETE, "drift_checks", drift_sql, drift_params)
            
            # Delete alerts
            alert_sql = "DELETE FROM alerts WHERE model_key = ?"
            alert_params = (model_key,)
            _queue_write("models", WriteOperation.DELETE, "alerts", alert_sql, alert_params)
            
            logger.info(f"Queued delete for model {model_key} (artifacts: {delete_artifacts})")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_key}: {e}")
            return False


class ClientDatasetRepository:
    """Repository for client datasets"""
    
    def create(self, dataset: ClientDataset) -> ClientDataset:
        """Create a new client dataset"""
        sql = """
            INSERT INTO client_datasets (
                dataset_id, model_key, dataset_version, created_at,
                item_count, confidence_threshold, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            dataset.dataset_id, dataset.model_key, dataset.dataset_version,
            dataset.created_at or datetime.now(),
            dataset.item_count, dataset.confidence_threshold, dataset.status
        )
        _queue_write("models", WriteOperation.CREATE, "client_datasets", sql, params)
        return dataset
    
    def get(self, dataset_id: str) -> Optional[ClientDataset]:
        """Get a dataset by ID"""
        with db_manager.models_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM client_datasets WHERE dataset_id = ?
            """, (dataset_id,)).fetchone()
            
            if row:
                return ClientDataset(
                    dataset_id=row['dataset_id'],
                    model_key=row['model_key'],
                    dataset_version=row['dataset_version'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    item_count=row['item_count'],
                    confidence_threshold=row['confidence_threshold'],
                    status=row['status']
                )
            return None
    
    def get_all(self) -> List[ClientDataset]:
        """Get all client datasets"""
        with db_manager.models_db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM client_datasets ORDER BY created_at DESC").fetchall()
            return [
                ClientDataset(
                    dataset_id=row['dataset_id'],
                    model_key=row['model_key'],
                    dataset_version=row['dataset_version'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    item_count=row['item_count'],
                    confidence_threshold=row['confidence_threshold'],
                    status=row['status']
                )
                for row in rows
            ]


class RetrainingJobRepository:
    """Repository for retraining jobs"""
    
    def create(self, job: RetrainingJob) -> RetrainingJob:
        """Create a new retraining job"""
        sql = """
            INSERT INTO retraining_jobs (
                job_id, model_key, source_model_version, new_model_version,
                old_metrics, new_metrics, accuracy_delta, status,
                created_at, completed_at, reverted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            job.job_id, job.model_key, job.source_model_version, job.new_model_version,
            job.old_metrics, job.new_metrics, job.accuracy_delta, job.status,
            job.created_at or datetime.now(), job.completed_at, job.reverted_at
        )
        _queue_write("models", WriteOperation.CREATE, "retraining_jobs", sql, params)
        return job
    
    def get(self, job_id: str) -> Optional[RetrainingJob]:
        """Get a retraining job by ID"""
        with db_manager.models_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM retraining_jobs WHERE job_id = ?
            """, (job_id,)).fetchone()
            
            if row:
                return RetrainingJob(
                    job_id=row['job_id'],
                    model_key=row['model_key'],
                    source_model_version=row['source_model_version'],
                    new_model_version=row['new_model_version'],
                    old_metrics=row['old_metrics'],
                    new_metrics=row['new_metrics'],
                    accuracy_delta=row['accuracy_delta'],
                    status=row['status'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    completed_at=parse_date(row['completed_at']) if row['completed_at'] else None,
                    reverted_at=parse_date(row['reverted_at']) if row['reverted_at'] else None
                )
            return None
    
    def get_all(self) -> List[RetrainingJob]:
        """Get all retraining jobs"""
        with db_manager.models_db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM retraining_jobs ORDER BY created_at DESC").fetchall()
            return [
                RetrainingJob(
                    job_id=row['job_id'],
                    model_key=row['model_key'],
                    source_model_version=row['source_model_version'],
                    new_model_version=row['new_model_version'],
                    old_metrics=row['old_metrics'],
                    new_metrics=row['new_metrics'],
                    accuracy_delta=row['accuracy_delta'],
                    status=row['status'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    completed_at=parse_date(row['completed_at']) if row['completed_at'] else None,
                    reverted_at=parse_date(row['reverted_at']) if row['reverted_at'] else None
                )
                for row in rows
            ]


class DriftCheckRepository:
    """Repository for drift checks"""
    
    def create(self, check: DriftCheck) -> DriftCheck:
        """Create a new drift check"""
        sql = """
            INSERT INTO drift_checks (
                check_id, model_key, check_date, psi_value,
                js_divergence, drift_detected, items_analyzed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            check.check_id, check.model_key, check.check_date, check.psi_value,
            check.js_divergence, check.drift_detected, check.items_analyzed,
            check.created_at or datetime.now()
        )
        _queue_write("models", WriteOperation.CREATE, "drift_checks", sql, params)
        return check
    
    def get(self, check_id: str) -> Optional[DriftCheck]:
        """Get a drift check by ID"""
        with db_manager.models_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM drift_checks WHERE check_id = ?
            """, (check_id,)).fetchone()
            
            if row:
                return DriftCheck(
                    check_id=row['check_id'],
                    model_key=row['model_key'],
                    check_date=parse_date(row['check_date']).date() if row['check_date'] else None,
                    psi_value=row['psi_value'],
                    js_divergence=row['js_divergence'],
                    drift_detected=bool(row['drift_detected']),
                    items_analyzed=row['items_analyzed'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None
                )
            return None
    
    def get_all(self, model_key: Optional[str] = None) -> List[DriftCheck]:
        """Get all drift checks, optionally filtered by model_key"""
        with db_manager.models_db.get_connection() as conn:
            if model_key:
                rows = conn.execute("""
                    SELECT * FROM drift_checks WHERE model_key = ? ORDER BY check_date DESC
                """, (model_key,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM drift_checks ORDER BY check_date DESC").fetchall()
            
            return [
                DriftCheck(
                    check_id=row['check_id'],
                    model_key=row['model_key'],
                    check_date=parse_date(row['check_date']).date() if row['check_date'] else None,
                    psi_value=row['psi_value'],
                    js_divergence=row['js_divergence'],
                    drift_detected=bool(row['drift_detected']),
                    items_analyzed=row['items_analyzed'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None
                )
                for row in rows
            ]


class AlertRepository:
    """Repository for alerts"""
    
    def create(self, alert: Alert) -> Alert:
        """Create a new alert"""
        sql = """
            INSERT INTO alerts (
                alert_id, type, severity, model_key, message, details,
                created_at, dismissed_at, dismissed_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            alert.alert_id, alert.type, alert.severity, alert.model_key,
            alert.message, alert.details, alert.created_at or datetime.now(),
            alert.dismissed_at, alert.dismissed_by
        )
        _queue_write("models", WriteOperation.CREATE, "alerts", sql, params)
        return alert
    
    def get(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID"""
        with db_manager.models_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM alerts WHERE alert_id = ?
            """, (alert_id,)).fetchone()
            
            if row:
                return Alert(
                    alert_id=row['alert_id'],
                    type=row['type'],
                    severity=row['severity'],
                    model_key=row['model_key'],
                    message=row['message'],
                    details=row['details'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    dismissed_at=parse_date(row['dismissed_at']) if row['dismissed_at'] else None,
                    dismissed_by=row['dismissed_by']
                )
            return None
    
    def get_all(self, dismissed: Optional[bool] = None) -> List[Alert]:
        """Get all alerts, optionally filtered by dismissed status"""
        with db_manager.models_db.get_connection() as conn:
            if dismissed is None:
                rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
            elif dismissed:
                rows = conn.execute("""
                    SELECT * FROM alerts WHERE dismissed_at IS NOT NULL ORDER BY created_at DESC
                """).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM alerts WHERE dismissed_at IS NULL ORDER BY created_at DESC
                """).fetchall()
            
            return [
                Alert(
                    alert_id=row['alert_id'],
                    type=row['type'],
                    severity=row['severity'],
                    model_key=row['model_key'],
                    message=row['message'],
                    details=row['details'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    dismissed_at=parse_date(row['dismissed_at']) if row['dismissed_at'] else None,
                    dismissed_by=row['dismissed_by']
                )
                for row in rows
            ]
    
    def get_active(self) -> List[Alert]:
        """Get all active (non-dismissed) alerts"""
        return self.get_all(dismissed=False)
    
    def dismiss(self, alert_id: str, dismissed_by: str) -> bool:
        """Dismiss an alert"""
        sql = "UPDATE alerts SET dismissed_at = ?, dismissed_by = ? WHERE alert_id = ?"
        params = (datetime.now(), dismissed_by, alert_id)
        _queue_write("models", WriteOperation.UPDATE, "alerts", sql, params)
        return True


class PredictionLogRepository:
    """Repository for prediction logs"""
    
    def create(self, log: PredictionLog) -> PredictionLog:
        """Create a new prediction log"""
        sql = """
            INSERT INTO prediction_logs (
                log_id, model_key, version, input_features,
                prediction, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            log.log_id, log.model_key, log.version, log.input_features,
            log.prediction, log.confidence, log.created_at or datetime.now()
        )
        _queue_write("models", WriteOperation.CREATE, "prediction_logs", sql, params)
        return log
    
    def get_all(self, model_key: Optional[str] = None, limit: int = 1000) -> List[PredictionLog]:
        """Get prediction logs, optionally filtered by model_key"""
        with db_manager.models_db.get_connection() as conn:
            if model_key:
                rows = conn.execute("""
                    SELECT * FROM prediction_logs 
                    WHERE model_key = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (model_key, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM prediction_logs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
            
            return [
                PredictionLog(
                    log_id=row['log_id'],
                    model_key=row['model_key'],
                    version=row['version'],
                    input_features=row['input_features'],  # Already bytes (BLOB)
                    prediction=row['prediction'] if isinstance(row['prediction'], bytes) else None,  # BLOB
                    confidence=row['confidence'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None
                )
                for row in rows
            ]


class JobRepository:
    """Repository for jobs"""
    
    def _row_to_job(self, row_dict: dict) -> Job:
        """Convert database row to Job object"""
        return Job(
            job_id=row_dict['job_id'],
            model_key=row_dict['model_key'],
            job_type=row_dict.get('job_type', 'train'),
            status=row_dict['status'],
            stage=row_dict.get('stage'),
            source=row_dict.get('source', 'api'),
            created_at=parse_date(row_dict['created_at']) if row_dict.get('created_at') else None,
            started_at=parse_date(row_dict['started_at']) if row_dict.get('started_at') else None,
            completed_at=parse_date(row_dict['completed_at']) if row_dict.get('completed_at') else None,
            dataset_size=row_dict.get('dataset_size'),
            metrics=row_dict.get('metrics'),
            error_message=row_dict.get('error_message'),
            client_ip=row_dict.get('client_ip'),
            user_agent=row_dict.get('user_agent'),
            priority=row_dict.get('priority', 5),
            user_tier=row_dict.get('user_tier', 'user'),
            data_size_bytes=row_dict.get('data_size_bytes'),
            progress_current=row_dict.get('progress_current', 0),
            progress_total=row_dict.get('progress_total', 100),
            model_version=row_dict.get('model_version'),
            assigned_worker_id=row_dict.get('assigned_worker_id'),
            request_payload=row_dict.get('request_payload'),
            result_payload=row_dict.get('result_payload'),
            user_os=row_dict.get('user_os'),
            user_device=row_dict.get('user_device'),
            user_cpu_cores=row_dict.get('user_cpu_cores'),
            user_ram_gb=row_dict.get('user_ram_gb'),
            user_gpu=row_dict.get('user_gpu'),
            user_id=row_dict.get('user_id')
        )
    
    def create(self, job: Job) -> Job:
        """Create a new job"""
        sql = """
            INSERT INTO jobs (
                job_id, model_key, job_type, status, stage, source,
                created_at, started_at, completed_at, dataset_size, metrics,
                error_message, client_ip, user_agent, priority, user_tier,
                data_size_bytes, progress_current, progress_total, model_version,
                assigned_worker_id, request_payload, result_payload, user_os,
                user_device, user_cpu_cores, user_ram_gb, user_gpu, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            job.job_id, job.model_key, job.job_type, job.status, job.stage, job.source,
            job.created_at or datetime.now(), job.started_at, job.completed_at,
            job.dataset_size, job.metrics, job.error_message, job.client_ip,
            job.user_agent, job.priority, job.user_tier, job.data_size_bytes,
            job.progress_current, job.progress_total, job.model_version,
            job.assigned_worker_id, job.request_payload, job.result_payload,
            job.user_os, job.user_device, job.user_cpu_cores, job.user_ram_gb, job.user_gpu, job.user_id
        )
        _queue_write("models", WriteOperation.CREATE, "jobs", sql, params)
        return job
    
    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        with db_manager.models_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM jobs WHERE job_id = ?
            """, (job_id,)).fetchone()
            
            if row:
                return self._row_to_job(dict(row))
            return None
    
    def update_status(
        self, job_id: str, status: str,
        metrics: Optional[dict] = None,
        error_message: Optional[str] = None,
        stage: Optional[str] = None
    ) -> bool:
        """Update job status"""
        updates = {"status": status}
        
        if status == "running":
            updates["started_at"] = datetime.now()
        elif status in ("completed", "failed"):
            updates["completed_at"] = datetime.now()
        
        if metrics:
            updates["metrics"] = json.dumps(metrics)
        
        if error_message:
            updates["error_message"] = error_message
        
        if stage:
            updates["stage"] = stage
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        sql = f"UPDATE jobs SET {set_clause} WHERE job_id = ?"
        params = tuple(list(updates.values()) + [job_id])
        _queue_write("models", WriteOperation.UPDATE, "jobs", sql, params)
        return True
    
    def get_all(
        self, 
        limit: int = 50, 
        offset: int = 0,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        model_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[Job]:
        """Get all jobs with optional filters"""
        with db_manager.models_db.get_connection() as conn:
            conditions = []
            params = []
            
            if job_type:
                conditions.append("job_type = ?")
                params.append(job_type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if model_key:
                conditions.append("model_key = ?")
                params.append(model_key)
            
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.extend([limit, offset])
            
            rows = conn.execute(f"""
                SELECT * FROM jobs 
                WHERE {where_clause}
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, params).fetchall()
            
            return [self._row_to_job(dict(row)) for row in rows]
    
    def get_queued_jobs(self, model_key: Optional[str] = None) -> List[Job]:
        """Get all queued jobs, optionally filtered by model_key"""
        with db_manager.models_db.get_connection() as conn:
            conditions = ["status = 'queued'"]
            params = []
            
            if model_key:
                conditions.append("model_key = ?")
                params.append(model_key)
            
            where_clause = " AND ".join(conditions)
            
            rows = conn.execute(f"""
                SELECT * FROM jobs 
                WHERE {where_clause}
                ORDER BY priority DESC, created_at ASC
            """, params).fetchall()
            
            return [self._row_to_job(dict(row)) for row in rows]
    
    def get_by_status(self, status: str, limit: Optional[int] = None) -> List[Job]:
        """Get jobs by status with optional limit"""
        with db_manager.models_db.get_connection() as conn:
            query = """
                SELECT * FROM jobs 
                WHERE status = ?
                ORDER BY created_at DESC
            """
            params = [status]
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_job(dict(row)) for row in rows]
    
    def update_priority(self, job_id: str, priority: int) -> bool:
        """Update job priority"""
        sql = "UPDATE jobs SET priority = ? WHERE job_id = ?"
        params = (priority, job_id)
        _queue_write("models", WriteOperation.UPDATE, "jobs", sql, params)
        return True
    
    def count_all(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        model_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> int:
        """Count jobs with optional filters"""
        with db_manager.models_db.get_connection() as conn:
            conditions = []
            params = []
            
            if job_type:
                conditions.append("job_type = ?")
                params.append(job_type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if model_key:
                conditions.append("model_key = ?")
                params.append(model_key)
            
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            row = conn.execute(f"""
                SELECT COUNT(*) as count FROM jobs WHERE {where_clause}
            """, params).fetchone()
            
            return row['count'] if row else 0


# Backward compatibility alias
TrainingJobRepository = JobRepository


# Specialized event repositories for logs database
class AlertEventRepository:
    """Repository for alert events"""
    
    def create(self, event_id: str, alert_id: str, event_type: str, severity: str, 
               model_key: Optional[str], message: str, details: Optional[str],
               client_ip: Optional[str], user_agent: Optional[str]) -> bool:
        """Create a new alert event"""
        sql = """
            INSERT INTO alert_events (
                event_id, alert_id, event_type, severity, model_key, message, details,
                created_at, client_ip, user_agent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event_id, alert_id, event_type, severity, model_key, message, details,
            datetime.now(), client_ip, user_agent
        )
        _queue_write("logs", WriteOperation.CREATE, "alert_events", sql, params)
        return True
    
    def get_all(self, limit: int = 50) -> List[dict]:
        """Get all alert events"""
        with db_manager.logs_db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM alert_events ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class TrainEventRepository:
    """Repository for training events"""
    
    def create(self, event_id: str, model_key: str, version: Optional[str], job_id: Optional[str],
               status: str, stage: Optional[str], metrics: Optional[str], error_message: Optional[str],
               duration_ms: Optional[int], data_size_bytes: Optional[int]) -> bool:
        """Create a new train event"""
        sql = """
            INSERT INTO train_events (
                event_id, model_key, version, job_id, status, stage, metrics, error_message,
                created_at, completed_at, duration_ms, data_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        completed_at = datetime.now() if status in ("completed", "failed") else None
        params = (
            event_id, model_key, version, job_id, status, stage, metrics, error_message,
            datetime.now(), completed_at, duration_ms, data_size_bytes
        )
        _queue_write("logs", WriteOperation.CREATE, "train_events", sql, params)
        return True
    
    def get_all(self, model_key: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all train events"""
        with db_manager.logs_db.get_connection() as conn:
            if model_key:
                rows = conn.execute("""
                    SELECT * FROM train_events WHERE model_key = ? ORDER BY created_at DESC LIMIT ?
                """, (model_key, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM train_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class PredictEventRepository:
    """Repository for prediction events"""
    
    def create(self, event_id: str, model_key: str, version: Optional[str], job_id: Optional[str],
               status: str, input_size: Optional[int], output_size: Optional[int],
               error_message: Optional[str], duration_ms: Optional[int], data_size_bytes: Optional[int],
               client_ip: Optional[str], user_agent: Optional[str], stage: Optional[str] = None,
               input_data: Optional[str] = None, output_data: Optional[str] = None) -> bool:
        """Create a new predict event"""
        sql = """
            INSERT INTO predict_events (
                event_id, model_key, version, job_id, status, stage, input_size, output_size,
                error_message, created_at, completed_at, duration_ms, data_size_bytes,
                client_ip, user_agent, input_data, output_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        completed_at = datetime.now() if status in ("completed", "failed") else None
        params = (
            event_id, model_key, version, job_id, status, stage, input_size, output_size,
            error_message, datetime.now(), completed_at, duration_ms, data_size_bytes,
            client_ip, user_agent, input_data, output_data
        )
        _queue_write("logs", WriteOperation.CREATE, "predict_events", sql, params)
        return True
    
    def get_all(self, model_key: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all predict events"""
        with db_manager.logs_db.get_connection() as conn:
            if model_key:
                rows = conn.execute("""
                    SELECT * FROM predict_events WHERE model_key = ? ORDER BY created_at DESC LIMIT ?
                """, (model_key, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM predict_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class LoginEventRepository:
    """Repository for login events"""
    
    def create(self, event_id: str, user_id: Optional[str], username: Optional[str],
               event_type: str, ip_address: Optional[str], user_agent: Optional[str],
               success: bool, error_message: Optional[str] = None) -> bool:
        """Create a new login event"""
        sql = """
            INSERT INTO login_events (
                event_id, user_id, username, event_type, ip_address, user_agent,
                success, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event_id, user_id, username, event_type, ip_address, user_agent,
            1 if success else 0, error_message, datetime.now()
        )
        _queue_write("logs", WriteOperation.CREATE, "login_events", sql, params)
        return True
    
    def get_all(self, user_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all login events"""
        with db_manager.logs_db.get_connection() as conn:
            if user_id:
                rows = conn.execute("""
                    SELECT * FROM login_events WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
                """, (user_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM login_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class SystemEventRepository:
    """Repository for system events"""
    
    def create(self, event_id: str, event_type: str, component: str, message: str,
               severity: str = "info", details: Optional[str] = None) -> bool:
        """Create a new system event"""
        sql = """
            INSERT INTO system_events (
                event_id, event_type, component, message, severity, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (event_id, event_type, component, message, severity, details, datetime.now())
        _queue_write("logs", WriteOperation.CREATE, "system_events", sql, params)
        return True
    
    def get_all(self, event_type: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all system events"""
        with db_manager.logs_db.get_connection() as conn:
            if event_type:
                rows = conn.execute("""
                    SELECT * FROM system_events WHERE event_type = ? ORDER BY created_at DESC LIMIT ?
                """, (event_type, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM system_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class DriftEventRepository:
    """Repository for drift events"""
    
    def create(self, event_id: str, model_key: str, check_id: Optional[str],
               drift_detected: bool, psi_value: Optional[float] = None,
               js_divergence: Optional[float] = None) -> bool:
        """Create a new drift event"""
        sql = """
            INSERT INTO drift_events (
                event_id, model_key, check_id, drift_detected, psi_value, js_divergence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (event_id, model_key, check_id, 1 if drift_detected else 0, psi_value, js_divergence, datetime.now())
        _queue_write("logs", WriteOperation.CREATE, "drift_events", sql, params)
        return True
    
    def get_all(self, model_key: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all drift events"""
        with db_manager.logs_db.get_connection() as conn:
            if model_key:
                rows = conn.execute("""
                    SELECT * FROM drift_events WHERE model_key = ? ORDER BY created_at DESC LIMIT ?
                """, (model_key, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM drift_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


class JobEventRepository:
    """Repository for job events"""
    
    def create(self, event_id: str, job_id: str, job_type: str, model_key: Optional[str],
               status: str, stage: Optional[str], error_message: Optional[str] = None) -> bool:
        """Create a new job event"""
        sql = """
            INSERT INTO job_events (
                event_id, job_id, job_type, model_key, status, stage, created_at, completed_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        completed_at = datetime.now() if status in ("completed", "failed") else None
        params = (event_id, job_id, job_type, model_key, status, stage, datetime.now(), completed_at, error_message)
        _queue_write("logs", WriteOperation.CREATE, "job_events", sql, params)
        return True
    
    def get_all(self, job_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Get all job events"""
        with db_manager.logs_db.get_connection() as conn:
            if job_id:
                rows = conn.execute("""
                    SELECT * FROM job_events WHERE job_id = ? ORDER BY created_at DESC LIMIT ?
                """, (job_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM job_events ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(row) for row in rows]


# Legacy EventRepository for backward compatibility (deprecated, use specialized repositories)
class EventRepository:
    """Legacy repository for events (deprecated - use specialized event repositories)"""
    
    def create(self, event: Event) -> Event:
        """Create a new event - routes to appropriate specialized repository"""
        event_type = event.event_type.lower() if event.event_type else ""
        
        if "alert" in event_type:
            AlertEventRepository().create(
                event.event_id, None, event.event_type, "info", event.model_key,
                event.input_data or "", event.output_data, event.client_ip, event.user_agent
            )
        elif "train" in event_type or event.source == "training":
            TrainEventRepository().create(
                event.event_id, event.model_key or "", None, None,
                event.status, event.stage, event.output_data, event.error_message,
                event.duration_ms, event.data_size_bytes
            )
        elif "predict" in event_type or event.source == "prediction":
            # Extract version and job_id from input_data if available
            version = None
            job_id = None
            input_size = None
            if event.input_data:
                try:
                    input_data_dict = json.loads(event.input_data) if isinstance(event.input_data, str) else event.input_data
                    version = input_data_dict.get("version")
                    job_id = input_data_dict.get("job_id")
                    data_count = input_data_dict.get("data_count")
                    if data_count:
                        input_size = data_count
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Serialize input_data and output_data to JSON strings if they are dicts
            input_data_str = event.input_data
            if input_data_str and not isinstance(input_data_str, str):
                input_data_str = json.dumps(input_data_str)
            
            output_data_str = event.output_data
            if output_data_str and not isinstance(output_data_str, str):
                output_data_str = json.dumps(output_data_str)
            
            PredictEventRepository().create(
                event.event_id, event.model_key or "", version, job_id,
                event.status, input_size, None, event.error_message,
                event.duration_ms, event.data_size_bytes, event.client_ip, event.user_agent,
                event.stage, input_data_str, output_data_str
            )
        elif "login" in event_type or event.source == "auth":
            LoginEventRepository().create(
                event.event_id, None, None, event.event_type,
                event.client_ip, event.user_agent, event.status == "completed"
            )
        elif "system" in event_type or event.source == "system":
            SystemEventRepository().create(
                event.event_id, event.event_type, event.source or "system",
                event.input_data or "", "info", event.output_data
            )
        elif "drift" in event_type:
            DriftEventRepository().create(
                event.event_id, event.model_key or "", None, False
            )
        elif "job" in event_type:
            JobEventRepository().create(
                event.event_id, None, event.event_type, event.model_key,
                event.status, event.stage, event.error_message
            )
        else:
            # Default to system events
            SystemEventRepository().create(
                event.event_id, event.event_type or "unknown", event.source or "system",
                event.input_data or "", "info", event.output_data
            )
        
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID (searches all event tables)"""
        # Try each event table
        for table_name in ["alert_events", "train_events", "predict_events", "login_events", 
                          "system_events", "drift_events", "job_events"]:
            with db_manager.logs_db.get_connection() as conn:
                row = conn.execute(f"SELECT * FROM {table_name} WHERE event_id = ?", (event_id,)).fetchone()
                if row:
                    return self._row_to_event(dict(row), table_name=table_name)
        return None
    
    def _row_to_event(self, row_dict: dict, table_name: Optional[str] = None) -> Event:
        """Convert database row to Event object"""
        # Determine event_type and source based on table_name if not in row_dict
        event_type = row_dict.get('event_type')
        if not event_type and table_name:
            if table_name == "predict_events":
                event_type = "predict"
            elif table_name == "train_events":
                event_type = "train"
            elif table_name == "alert_events":
                event_type = "alert"
            elif table_name == "login_events":
                event_type = "login"
            elif table_name == "system_events":
                event_type = "system"
            elif table_name == "drift_events":
                event_type = "drift"
            elif table_name == "job_events":
                event_type = "job"
        
        # Extract input_data and output_data based on table type
        input_data = None
        output_data = None
        
        if table_name == "predict_events":
            input_data = row_dict.get('input_data')
            output_data = row_dict.get('output_data')
        elif table_name == "train_events":
            input_data = row_dict.get('input_data')
            output_data = row_dict.get('metrics')
        elif table_name == "alert_events":
            input_data = row_dict.get('message')
            output_data = row_dict.get('details')
        elif table_name == "system_events":
            input_data = row_dict.get('message')
            output_data = row_dict.get('details')
        else:
            # Fallback for other tables
            input_data = row_dict.get('input_data') or row_dict.get('message') or row_dict.get('details')
            output_data = row_dict.get('output_data') or row_dict.get('metrics') or row_dict.get('details')
        
        return Event(
            event_id=row_dict['event_id'],
            event_type=event_type or row_dict.get('event_type', 'unknown'),
            source=row_dict.get('source', 'system'),
            model_key=row_dict.get('model_key'),
            status=row_dict.get('status', 'queued'),
            stage=row_dict.get('stage'),
            input_data=input_data,
            output_data=output_data,
            user_agent=row_dict.get('user_agent'),
            client_ip=row_dict.get('client_ip') or row_dict.get('ip_address'),
            created_at=parse_date(row_dict['created_at']) if row_dict.get('created_at') else None,
            completed_at=parse_date(row_dict['completed_at']) if row_dict.get('completed_at') else None,
            error_message=row_dict.get('error_message'),
            duration_ms=row_dict.get('duration_ms'),
            display_format=row_dict.get('display_format', 'table'),
            data_size_bytes=row_dict.get('data_size_bytes')
        )
    
    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        model_key: Optional[str] = None,
        client_ip: Optional[str] = None,
        source: Optional[str] = None
    ) -> List[Event]:
        """Get all events with optional filters (searches all event tables)"""
        all_events = []
        
        # Search all event tables and combine results
        with db_manager.logs_db.get_connection() as conn:
            # Build query for each table
            tables_to_search = []
            if not event_type or event_type.lower() in ["train", "retrain"]:
                tables_to_search.append(("train_events", "train"))
            if not event_type or event_type.lower() == "predict":
                tables_to_search.append(("predict_events", "predict"))
            if not event_type or event_type.lower() == "drift":
                tables_to_search.append(("drift_events", "drift"))
            if not event_type or event_type.lower() in ["alert", "warning"]:
                tables_to_search.append(("alert_events", "alert"))
            if not event_type or event_type.lower() == "login":
                tables_to_search.append(("login_events", "login"))
            if not event_type or event_type.lower() == "system":
                tables_to_search.append(("system_events", "system"))
            if not event_type or event_type.lower() == "job":
                tables_to_search.append(("job_events", "job"))
            
            for table_name, default_type in tables_to_search:
                conditions = []
                params = []
                
                if event_type and event_type.lower() not in [default_type, "retrain"]:
                    continue
                
                if status:
                    if table_name in ["train_events", "predict_events", "job_events"]:
                        conditions.append("status = ?")
                        params.append(status)
                
                if model_key:
                    if table_name in ["train_events", "predict_events", "drift_events", "job_events"]:
                        conditions.append("model_key = ?")
                        params.append(model_key)
                
                if client_ip:
                    if table_name in ["predict_events", "login_events", "alert_events"]:
                        if table_name == "predict_events":
                            conditions.append("client_ip = ?")
                            params.append(client_ip)
                        elif table_name == "login_events":
                            conditions.append("ip_address = ?")
                            params.append(client_ip)
                        elif table_name == "alert_events":
                            conditions.append("client_ip = ?")
                            params.append(client_ip)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                params.extend([limit + offset, offset])
                
                try:
                    rows = conn.execute(f"""
                        SELECT * FROM {table_name}
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                    """, params).fetchall()
                    
                    for row in rows:
                        row_dict = dict(row)
                        # Convert to Event object
                        # Extract input_data and output_data based on table type
                        input_data = None
                        output_data = None
                        
                        if table_name == "predict_events":
                            input_data = row_dict.get('input_data')
                            output_data = row_dict.get('output_data')
                        elif table_name == "train_events":
                            input_data = row_dict.get('input_data')
                            output_data = row_dict.get('metrics')
                        elif table_name == "alert_events":
                            input_data = row_dict.get('message')
                            output_data = row_dict.get('details')
                        elif table_name == "system_events":
                            input_data = row_dict.get('message')
                            output_data = row_dict.get('details')
                        else:
                            # Fallback for other tables
                            input_data = row_dict.get('input_data') or row_dict.get('message') or row_dict.get('details')
                            output_data = row_dict.get('output_data') or row_dict.get('metrics') or row_dict.get('details')
                        
                        event = Event(
                            event_id=row_dict.get('event_id', ''),
                            event_type=default_type if not event_type else event_type,
                            source=row_dict.get('source', 'system'),
                            model_key=row_dict.get('model_key'),
                            status=row_dict.get('status', 'queued'),
                            stage=row_dict.get('stage'),
                            input_data=input_data,
                            output_data=output_data,
                            user_agent=row_dict.get('user_agent'),
                            client_ip=row_dict.get('client_ip') or row_dict.get('ip_address'),
                            created_at=parse_date(row_dict['created_at']) if row_dict.get('created_at') else None,
                            completed_at=parse_date(row_dict['completed_at']) if row_dict.get('completed_at') else None,
                            error_message=row_dict.get('error_message'),
                            duration_ms=row_dict.get('duration_ms'),
                            display_format=row_dict.get('display_format', 'table'),
                            data_size_bytes=row_dict.get('data_size_bytes')
                        )
                        all_events.append(event)
                except Exception as e:
                    logger.warning(f"Error reading from {table_name}: {e}")
                    continue
        
        # Sort by created_at descending and apply limit/offset
        all_events.sort(key=lambda e: e.created_at or datetime.min, reverse=True)
        return all_events[offset:offset + limit]
    
    def get_by_ip(self, client_ip: str, limit: int = 50) -> List[Event]:
        """Get all events from a specific IP address"""
        return self.get_all(limit=limit, client_ip=client_ip)
    
    def get_suspicious_events(self, limit: int = 50) -> List[Event]:
        """Get suspicious events (multiple events from same IP or unusual User-Agent)"""
        # Check login_events and predict_events for suspicious IPs
        with db_manager.logs_db.get_connection() as conn:
            # Find IPs with multiple events
            rows = conn.execute("""
                SELECT e.* FROM events e
                INNER JOIN (
                    SELECT client_ip, COUNT(*) as cnt
                    FROM events
                    WHERE client_ip IS NOT NULL
                    GROUP BY client_ip
                    HAVING cnt > 10
                ) suspicious_ips ON e.client_ip = suspicious_ips.client_ip
                ORDER BY e.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                Event(
                    event_id=row_dict['event_id'],
                    event_type=row_dict['event_type'],
                    source=row_dict['source'],
                    model_key=row_dict.get('model_key'),
                    status=row_dict['status'],
                    stage=row_dict.get('stage'),
                    input_data=row_dict.get('input_data'),
                    output_data=row_dict.get('output_data'),
                    user_agent=row_dict.get('user_agent'),
                    client_ip=row_dict.get('client_ip'),
                    created_at=parse_date(row_dict['created_at']) if row_dict.get('created_at') else None,
                    completed_at=parse_date(row_dict['completed_at']) if row_dict.get('completed_at') else None,
                    error_message=row_dict.get('error_message'),
                    duration_ms=row_dict.get('duration_ms'),
                    display_format=row_dict.get('display_format', 'table'),
                    data_size_bytes=row_dict.get('data_size_bytes')
                )
                for row in rows
                for row_dict in [dict(row)]
            ]
    
    def update_status(
        self, 
        event_id: str, 
        status: str,
        stage: Optional[str] = None,
        output_data: Optional[str] = None,
        input_data: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Update event status (updates in appropriate table)"""
        # Search all event tables to find the event
        tables_to_search = [
            "train_events", "predict_events", "drift_events", 
            "alert_events", "login_events", "system_events", "job_events"
        ]
        
        # Retry logic: events may be queued and not yet written to DB
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            with db_manager.logs_db.get_connection() as conn:
                for table_name in tables_to_search:
                    try:
                        # Check if event exists in this table
                        event_row = conn.execute(
                            f"SELECT event_id FROM {table_name} WHERE event_id = ?",
                            (event_id,)
                        ).fetchone()
                        
                        if event_row:
                            # Build update query based on table structure
                            updates = []
                            update_params = []
                            
                            updates.append("status = ?")
                            update_params.append(status)
                            
                            if stage is not None:
                                if table_name in ["train_events", "predict_events", "job_events"]:
                                    updates.append("stage = ?")
                                    update_params.append(stage)
                            
                            if output_data is not None:
                                if table_name == "train_events":
                                    updates.append("metrics = ?")
                                    update_params.append(output_data)
                                elif table_name == "predict_events":
                                    updates.append("output_data = ?")
                                    update_params.append(output_data)
                            
                            if input_data is not None:
                                if table_name == "predict_events":
                                    updates.append("input_data = ?")
                                    update_params.append(input_data)
                            
                            if error_message is not None:
                                if table_name in ["train_events", "predict_events", "job_events", "login_events"]:
                                    updates.append("error_message = ?")
                                    update_params.append(error_message)
                            
                            if duration_ms is not None:
                                if table_name in ["train_events", "predict_events"]:
                                    updates.append("duration_ms = ?")
                                    update_params.append(duration_ms)
                            
                            # Set completed_at if status is completed or failed
                            if status in ("completed", "failed"):
                                if table_name in ["train_events", "predict_events", "job_events", "login_events"]:
                                    updates.append("completed_at = ?")
                                    update_params.append(datetime.now())
                            
                            # Build SQL update statement
                            set_clause = ", ".join(updates)
                            update_params.append(event_id)
                            
                            sql = f"UPDATE {table_name} SET {set_clause} WHERE event_id = ?"
                            _queue_write("logs", WriteOperation.UPDATE, table_name, sql, tuple(update_params))
                            
                            logger.debug(f"Updated event {event_id} in {table_name}: status={status}, stage={stage}")
                            return True
                            
                    except Exception as e:
                        logger.warning(f"Error updating event in {table_name}: {e}")
                        continue
            
            # Event not found - may be queued, retry after delay
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                logger.warning(f"Event {event_id} not found in any event table after {max_retries} attempts")
        
        return False
    
    def update_display_format(self, event_id: str, display_format: str) -> bool:
        """Update event display format (deprecated - events don't have display_format in new schema)"""
        return False  # Not applicable to new schema


class ApiTokenRepository:
    """Repository for API tokens"""
    
    def _execute_with_retry(self, operation, *args, max_retries=10, retry_delay=0.1):
        """Execute a database operation with retry logic for database locks
        
        Note: SQLite with WAL mode and busy_timeout should handle most lock situations
        automatically. This retry is a fallback for edge cases.
        """
        for attempt in range(max_retries):
            try:
                return operation(*args)
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "database is locked" in error_msg and attempt < max_retries - 1:
                    # Exponential backoff with jitter, but respect busy_timeout
                    # Since busy_timeout is 60s, we use shorter retries as fallback
                    wait_time = retry_delay * (2 ** min(attempt, 4)) + (time.time() % 0.01)
                    wait_time = min(wait_time, 0.5)  # Cap at 0.5 second to avoid blocking too long
                    logger.warning(f"Database locked, retrying in {wait_time:.3f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    # Don't retry on other OperationalError (like FOREIGN KEY constraint)
                    logger.error(f"Database operation failed: {e}")
                    raise
            except sqlite3.IntegrityError as e:
                # Don't retry on integrity errors (FOREIGN KEY, UNIQUE, etc.)
                logger.error(f"Database integrity error: {e}")
                raise
            except Exception as e:
                # Re-raise non-database exceptions immediately
                logger.error(f"Database operation failed with unexpected error: {e}")
                raise
    
    def create(self, token: ApiToken) -> ApiToken:
        """Create a new API token using queue-based write"""
        # Prepare SQL and params for queue
        sql = """
            INSERT INTO api_tokens (
                token_id, token_hash, user_id, token_type, name,
                created_at, expires_at, last_used_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            token.token_id, token.token_hash, token.user_id, token.token_type, token.name,
            token.created_at or datetime.now(), token.expires_at, token.last_used_at, token.is_active
        )
        
        # Queue write operation
        db_manager.users_db.queue_write(
            WriteOperation.CREATE,
            "api_tokens",
            {"sql": sql, "params": params}
        )
        return token
    
    def get_by_hash(self, token_hash: str) -> Optional[ApiToken]:
        """Get token by hash for validation"""
        with db_manager.users_db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM api_tokens WHERE token_hash = ? AND is_active = 1
            """, (token_hash,)).fetchone()
            
            if row:
                # Check if token is expired
                if row['expires_at']:
                    expires_at = parse_date(row['expires_at'])
                    if expires_at < datetime.now():
                        return None
                
                return ApiToken(
                    token_id=row['token_id'],
                    token_hash=row['token_hash'],
                    user_id=row['user_id'],
                    token_type=row['token_type'],
                    name=row['name'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    expires_at=parse_date(row['expires_at']) if row['expires_at'] else None,
                    last_used_at=parse_date(row['last_used_at']) if row['last_used_at'] else None,
                    is_active=row['is_active']
                )
            return None
    
    def get_by_user(self, user_id: str, token_type: Optional[str] = None) -> List[ApiToken]:
        """Get all tokens for a user, optionally filtered by type"""
        with db_manager.users_db.get_connection() as conn:
            if token_type:
                rows = conn.execute("""
                    SELECT * FROM api_tokens 
                    WHERE user_id = ? AND token_type = ?
                    ORDER BY created_at DESC
                """, (user_id, token_type)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM api_tokens 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,)).fetchall()
            
            return [
                ApiToken(
                    token_id=row['token_id'],
                    token_hash=row['token_hash'],
                    user_id=row['user_id'],
                    token_type=row['token_type'],
                    name=row['name'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    expires_at=parse_date(row['expires_at']) if row['expires_at'] else None,
                    last_used_at=parse_date(row['last_used_at']) if row['last_used_at'] else None,
                    is_active=row['is_active']
                )
                for row in rows
            ]
    
    def get_all(self, token_type: Optional[str] = None) -> List[ApiToken]:
        """Get all tokens, optionally filtered by type"""
        with db_manager.users_db.get_connection() as conn:
            if token_type:
                rows = conn.execute("""
                    SELECT * FROM api_tokens 
                    WHERE token_type = ?
                    ORDER BY created_at DESC
                """, (token_type,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM api_tokens 
                    ORDER BY created_at DESC
                """).fetchall()
            
            return [
                ApiToken(
                    token_id=row['token_id'],
                    token_hash=row['token_hash'],
                    user_id=row['user_id'],
                    token_type=row['token_type'],
                    name=row['name'],
                    created_at=parse_date(row['created_at']) if row['created_at'] else None,
                    expires_at=parse_date(row['expires_at']) if row['expires_at'] else None,
                    last_used_at=parse_date(row['last_used_at']) if row['last_used_at'] else None,
                    is_active=row['is_active']
                )
                for row in rows
            ]
    
    def revoke(self, token_id: str) -> bool:
        """Revoke a token (set is_active = 0)"""
        sql = "UPDATE api_tokens SET is_active = 0 WHERE token_id = ?"
        params = (token_id,)
        _queue_write("users", WriteOperation.UPDATE, "api_tokens", sql, params)
        return True
    
    def delete(self, token_id: str) -> bool:
        """Delete a token"""
        sql = "DELETE FROM api_tokens WHERE token_id = ?"
        params = (token_id,)
        _queue_write("users", WriteOperation.DELETE, "api_tokens", sql, params)
        return True
    
    def update_last_used(self, token_id: str) -> bool:
        """Update last_used_at timestamp"""
        sql = "UPDATE api_tokens SET last_used_at = ? WHERE token_id = ?"
        params = (datetime.now(), token_id)
        _queue_write("users", WriteOperation.UPDATE, "api_tokens", sql, params)
        return True
    
    def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke all session tokens for a user"""
        sql = "UPDATE api_tokens SET is_active = 0 WHERE user_id = ? AND token_type = 'session'"
        params = (user_id,)
        _queue_write("users", WriteOperation.UPDATE, "api_tokens", sql, params)
        return True
    
    def revoke_all_tokens(self, user_id: str) -> bool:
        """Revoke all tokens (sessions and API) for a user"""
        sql = "UPDATE api_tokens SET is_active = 0 WHERE user_id = ?"
        params = (user_id,)
        _queue_write("users", WriteOperation.UPDATE, "api_tokens", sql, params)
        return True

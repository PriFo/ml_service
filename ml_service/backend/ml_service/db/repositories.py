"""Database repositories for CRUD operations"""
import json
import uuid
import logging
import time
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Optional
from dateutil.parser import parse as parse_date

from ml_service.db.connection import db

logger = logging.getLogger(__name__)
from ml_service.db.models import (
    Model, Job, TrainingJob, ClientDataset, RetrainingJob, DriftCheck, Alert, PredictionLog, Event, ApiToken
)


class ModelRepository:
    """Repository for models"""
    
    def create(self, model: Model) -> Model:
        """Create a new model or update if exists (same model_key and version)"""
        with db.get_connection() as conn:
            # Check if model with same key and version exists
            existing = conn.execute("""
                SELECT * FROM models WHERE model_key = ? AND version = ?
            """, (model.model_key, model.version)).fetchone()
            
            if existing:
                # Update existing model
                conn.execute("""
                    UPDATE models SET
                        status = ?, accuracy = ?, last_trained = ?, last_updated = ?,
                        task_type = ?, target_field = ?, feature_fields = ?
                    WHERE model_key = ? AND version = ?
                """, (
                    model.status, model.accuracy,
                    model.last_trained or datetime.now(),
                    datetime.now(),
                    model.task_type, model.target_field, model.feature_fields,
                    model.model_key, model.version
                ))
                logger.info(f"Updated existing model {model.model_key} v{model.version}")
            else:
                # Try to create new model - use INSERT OR REPLACE to handle PRIMARY KEY conflicts
                # This works for both single-column and composite PRIMARY KEY
                try:
                    conn.execute("""
                        INSERT INTO models (
                            model_key, version, status, accuracy, created_at,
                            last_trained, last_updated, task_type, target_field, feature_fields
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        model.model_key, model.version, model.status, model.accuracy,
                        model.created_at or datetime.now(),
                        model.last_trained, datetime.now(),
                        model.task_type, model.target_field, model.feature_fields
                    ))
                    logger.info(f"Created new model {model.model_key} v{model.version}")
                except Exception as e:
                    # If PRIMARY KEY conflict (old schema with single-column PK), update instead
                    if "UNIQUE constraint" in str(e) or "PRIMARY KEY" in str(e):
                        logger.warning(f"PRIMARY KEY conflict for {model.model_key}, updating existing model instead")
                        conn.execute("""
                            UPDATE models SET
                                version = ?, status = ?, accuracy = ?, last_trained = ?, last_updated = ?,
                                task_type = ?, target_field = ?, feature_fields = ?
                            WHERE model_key = ?
                        """, (
                            model.version, model.status, model.accuracy,
                            model.last_trained or datetime.now(),
                            datetime.now(),
                            model.task_type, model.target_field, model.feature_fields,
                            model.model_key
                        ))
                        logger.info(f"Updated existing model {model.model_key} to version {model.version}")
                    else:
                        raise
        return model
    
    def get(self, model_key: str, version: Optional[str] = None) -> Optional[Model]:
        """Get a model by key and optionally version"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        
        with db.get_connection() as conn:
            conn.execute(f"""
                UPDATE models SET {set_clause} WHERE model_key = ?
            """, list(kwargs.values()) + [model_key])
        return True


class ClientDatasetRepository:
    """Repository for client datasets"""
    
    def create(self, dataset: ClientDataset) -> ClientDataset:
        """Create a new client dataset"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO client_datasets (
                    dataset_id, model_key, dataset_version, created_at,
                    item_count, confidence_threshold, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset.dataset_id, dataset.model_key, dataset.dataset_version,
                dataset.created_at or datetime.now(),
                dataset.item_count, dataset.confidence_threshold, dataset.status
            ))
        return dataset
    
    def get(self, dataset_id: str) -> Optional[ClientDataset]:
        """Get a dataset by ID"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO retraining_jobs (
                    job_id, model_key, source_model_version, new_model_version,
                    old_metrics, new_metrics, accuracy_delta, status,
                    created_at, completed_at, reverted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.model_key, job.source_model_version, job.new_model_version,
                job.old_metrics, job.new_metrics, job.accuracy_delta, job.status,
                job.created_at or datetime.now(), job.completed_at, job.reverted_at
            ))
        return job
    
    def get(self, job_id: str) -> Optional[RetrainingJob]:
        """Get a retraining job by ID"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO drift_checks (
                    check_id, model_key, check_date, psi_value,
                    js_divergence, drift_detected, items_analyzed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                check.check_id, check.model_key, check.check_date, check.psi_value,
                check.js_divergence, check.drift_detected, check.items_analyzed,
                check.created_at or datetime.now()
            ))
        return check
    
    def get(self, check_id: str) -> Optional[DriftCheck]:
        """Get a drift check by ID"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO alerts (
                    alert_id, type, severity, model_key, message, details,
                    created_at, dismissed_at, dismissed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.type, alert.severity, alert.model_key,
                alert.message, alert.details, alert.created_at or datetime.now(),
                alert.dismissed_at, alert.dismissed_by
            ))
        return alert
    
    def get(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
            conn.execute("""
                UPDATE alerts SET dismissed_at = ?, dismissed_by = ? WHERE alert_id = ?
            """, (datetime.now(), dismissed_by, alert_id))
        return True


class PredictionLogRepository:
    """Repository for prediction logs"""
    
    def create(self, log: PredictionLog) -> PredictionLog:
        """Create a new prediction log"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO prediction_logs (
                    log_id, model_key, version, input_features,
                    prediction, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                log.log_id, log.model_key, log.version, log.input_features,
                log.prediction, log.confidence, log.created_at or datetime.now()
            ))
        return log
    
    def get_all(self, model_key: Optional[str] = None, limit: int = 1000) -> List[PredictionLog]:
        """Get prediction logs, optionally filtered by model_key"""
        with db.get_connection() as conn:
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
                    input_features=row['input_features'],
                    prediction=row['prediction'],
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
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, model_key, job_type, status, stage, source,
                    created_at, started_at, completed_at, dataset_size, metrics,
                    error_message, client_ip, user_agent, priority, user_tier,
                    data_size_bytes, progress_current, progress_total, model_version,
                    assigned_worker_id, request_payload, result_payload, user_os,
                    user_device, user_cpu_cores, user_ram_gb, user_gpu, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.model_key, job.job_type, job.status, job.stage, job.source,
                job.created_at or datetime.now(), job.started_at, job.completed_at,
                job.dataset_size, job.metrics, job.error_message, job.client_ip,
                job.user_agent, job.priority, job.user_tier, job.data_size_bytes,
                job.progress_current, job.progress_total, job.model_version,
                job.assigned_worker_id, job.request_payload, job.result_payload,
                job.user_os, job.user_device, job.user_cpu_cores, job.user_ram_gb, job.user_gpu, job.user_id
            ))
        return job
    
    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
            conn.execute(f"""
                UPDATE jobs SET {set_clause} WHERE job_id = ?
            """, list(updates.values()) + [job_id])
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
            conn.execute("""
                UPDATE jobs SET priority = ? WHERE job_id = ?
            """, (priority, job_id))
        return True
    
    def count_all(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        model_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> int:
        """Count jobs with optional filters"""
        with db.get_connection() as conn:
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


class EventRepository:
    """Repository for events"""
    
    def create(self, event: Event) -> Event:
        """Create a new event"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO events (
                    event_id, event_type, source, model_key, status, stage,
                    input_data, output_data, user_agent, client_ip, created_at,
                    completed_at, error_message, duration_ms, display_format, data_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.event_type, event.source, event.model_key,
                event.status, event.stage, event.input_data, event.output_data,
                event.user_agent, event.client_ip, event.created_at or datetime.now(),
                event.completed_at, event.error_message, event.duration_ms,
                event.display_format, event.data_size_bytes
            ))
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID"""
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM events WHERE event_id = ?
            """, (event_id,)).fetchone()
            
            if row:
                return self._row_to_event(dict(row))
            return None
    
    def _row_to_event(self, row_dict: dict) -> Event:
        """Convert database row to Event object"""
        return Event(
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
        """Get all events with optional filters"""
        with db.get_connection() as conn:
            conditions = []
            params = []
            
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if model_key:
                conditions.append("model_key = ?")
                params.append(model_key)
            
            if client_ip:
                conditions.append("client_ip = ?")
                params.append(client_ip)
            
            if source:
                conditions.append("source = ?")
                params.append(source)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.extend([limit, offset])
            
            rows = conn.execute(f"""
                SELECT * FROM events 
                WHERE {where_clause}
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, params).fetchall()
            
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
    
    def get_by_ip(self, client_ip: str, limit: int = 50) -> List[Event]:
        """Get all events from a specific IP address"""
        return self.get_all(limit=limit, client_ip=client_ip)
    
    def get_suspicious_events(self, limit: int = 50) -> List[Event]:
        """Get suspicious events (multiple events from same IP or unusual User-Agent)"""
        with db.get_connection() as conn:
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
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Update event status"""
        with db.get_connection() as conn:
            updates = {"status": status}
            
            if status in ("completed", "failed"):
                updates["completed_at"] = datetime.now()
            
            if stage:
                updates["stage"] = stage
            
            if output_data:
                updates["output_data"] = output_data
            
            if error_message:
                updates["error_message"] = error_message
            
            if duration_ms is not None:
                updates["duration_ms"] = duration_ms
            
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            conn.execute(f"""
                UPDATE events SET {set_clause} WHERE event_id = ?
            """, list(updates.values()) + [event_id])
            return True
    
    def update_display_format(self, event_id: str, display_format: str) -> bool:
        """Update event display format"""
        if display_format not in ('table', 'list', 'card'):
            return False
        with db.get_connection() as conn:
            conn.execute("UPDATE events SET display_format = ? WHERE event_id = ?", (display_format, event_id))
            return True


class ApiTokenRepository:
    """Repository for API tokens"""
    
    def _execute_with_retry(self, operation, *args, max_retries=10, retry_delay=0.05):
        """Execute a database operation with retry logic for database locks"""
        for attempt in range(max_retries):
            try:
                return operation(*args)
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "database is locked" in error_msg and attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = retry_delay * (2 ** attempt) + (time.time() % 0.01)
                    wait_time = min(wait_time, 1.0)  # Cap at 1 second
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
        """Create a new API token with retry logic for database locks"""
        def _create():
            with db.get_connection() as conn:
                # Use BEGIN IMMEDIATE to acquire write lock immediately
                # This helps prevent database locked errors in concurrent scenarios
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("""
                    INSERT INTO api_tokens (
                        token_id, token_hash, user_id, token_type, name,
                        created_at, expires_at, last_used_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    token.token_id, token.token_hash, token.user_id, token.token_type, token.name,
                    token.created_at or datetime.now(), token.expires_at, token.last_used_at, token.is_active
                ))
                # Commit is handled by context manager's __exit__
            return token
        
        return self._execute_with_retry(_create)
    
    def get_by_hash(self, token_hash: str) -> Optional[ApiToken]:
        """Get token by hash for validation"""
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        with db.get_connection() as conn:
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
        def _revoke():
            with db.get_connection() as conn:
                conn.execute("""
                    UPDATE api_tokens SET is_active = 0 WHERE token_id = ?
                """, (token_id,))
            return True
        
        return self._execute_with_retry(_revoke)
    
    def delete(self, token_id: str) -> bool:
        """Delete a token"""
        def _delete():
            with db.get_connection() as conn:
                conn.execute("""
                    DELETE FROM api_tokens WHERE token_id = ?
                """, (token_id,))
            return True
        
        return self._execute_with_retry(_delete)
    
    def update_last_used(self, token_id: str) -> bool:
        """Update last_used_at timestamp"""
        def _update():
            with db.get_connection() as conn:
                conn.execute("""
                    UPDATE api_tokens SET last_used_at = ? WHERE token_id = ?
                """, (datetime.now(), token_id))
            return True
        
        return self._execute_with_retry(_update)
    
    def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke all session tokens for a user"""
        def _revoke_all():
            with db.get_connection() as conn:
                conn.execute("""
                    UPDATE api_tokens SET is_active = 0 
                    WHERE user_id = ? AND token_type = 'session'
                """, (user_id,))
            return True
        
        return self._execute_with_retry(_revoke_all)
    
    def revoke_all_tokens(self, user_id: str) -> bool:
        """Revoke all tokens (sessions and API) for a user"""
        def _revoke_all():
            with db.get_connection() as conn:
                conn.execute("""
                    UPDATE api_tokens SET is_active = 0 
                    WHERE user_id = ?
                """, (user_id,))
            return True
        
        return self._execute_with_retry(_revoke_all)

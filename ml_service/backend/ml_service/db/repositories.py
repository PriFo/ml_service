"""Database repositories for CRUD operations"""
import json
import uuid
from datetime import datetime, date
from typing import List, Optional
from dateutil.parser import parse as parse_date

from ml_service.db.connection import db
from ml_service.db.models import (
    Model, Job, TrainingJob, ClientDataset, RetrainingJob, DriftCheck, Alert, PredictionLog, Event
)


class ModelRepository:
    """Repository for models"""
    
    def create(self, model: Model) -> Model:
        """Create a new model"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO models (
                    model_key, version, status, accuracy, created_at,
                    last_trained, last_updated, task_type, target_field, feature_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model.model_key, model.version, model.status, model.accuracy,
                model.created_at or datetime.now(),
                model.last_trained, model.last_updated,
                model.task_type, model.target_field, model.feature_fields
            ))
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


class JobRepository:
    """Repository for jobs (supports train, predict, drift, other)"""
    
    def create(self, job: Job) -> Job:
        """Create a new job"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, model_key, job_type, status, stage, source,
                    created_at, started_at, completed_at, dataset_size,
                    metrics, error_message, client_ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.model_key, job.job_type, job.status, job.stage, job.source,
                job.created_at or datetime.now(),
                job.started_at, job.completed_at,
                job.dataset_size, job.metrics, job.error_message,
                job.client_ip, job.user_agent
            ))
        return job
    
    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM jobs WHERE job_id = ?
            """, (job_id,)).fetchone()
            
            if row:
                row_dict = dict(row)
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
                    user_agent=row_dict.get('user_agent')
                )
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
    
    def get_all(self, limit: int = 50, job_type: Optional[str] = None) -> List[Job]:
        """Get all jobs, optionally filtered by type"""
        with db.get_connection() as conn:
            if job_type:
                rows = conn.execute("""
                    SELECT * FROM jobs 
                    WHERE job_type = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (job_type, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM jobs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
            return [
                Job(
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
                    user_agent=row_dict.get('user_agent')
                )
                for row in rows
                for row_dict in [dict(row)]
            ]
    
    def get_by_model(self, model_key: str, limit: int = 50) -> List[Job]:
        """Get jobs for a specific model"""
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM jobs 
                WHERE model_key = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (model_key, limit)).fetchall()
            return [
                Job(
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
                    user_agent=row_dict.get('user_agent')
                )
                for row in rows
                for row_dict in [dict(row)]
            ]
    
    def get_by_status(self, status: str, limit: int = 50) -> List[Job]:
        """Get jobs by status"""
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM jobs 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (status, limit)).fetchall()
            return [
                Job(
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
                    user_agent=row_dict.get('user_agent')
                )
                for row in rows
                for row_dict in [dict(row)]
            ]


# Backward compatibility alias
TrainingJobRepository = JobRepository


class DriftCheckRepository:
    """Repository for drift checks"""
    
    def create_drift_check(
        self, model_key: str, check_date: date,
        psi_value: Optional[float] = None,
        js_divergence: Optional[float] = None,
        drift_detected: bool = False,
        items_analyzed: Optional[int] = None
    ) -> DriftCheck:
        """Create a drift check record"""
        check_id = str(uuid.uuid4())
        drift_check = DriftCheck(
            check_id=check_id,
            model_key=model_key,
            check_date=check_date,
            psi_value=psi_value,
            js_divergence=js_divergence,
            drift_detected=drift_detected,
            items_analyzed=items_analyzed,
            created_at=datetime.now()
        )
        
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO drift_checks (
                    check_id, model_key, check_date, psi_value,
                    js_divergence, drift_detected, items_analyzed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                drift_check.check_id, drift_check.model_key,
                drift_check.check_date, drift_check.psi_value,
                drift_check.js_divergence, drift_check.drift_detected,
                drift_check.items_analyzed, drift_check.created_at
            ))
        
        return drift_check
    
    def get_drift_history(self, model_key: str, limit: int = 30) -> List[DriftCheck]:
        """Get drift check history for a model"""
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM drift_checks 
                WHERE model_key = ? 
                ORDER BY check_date DESC 
                LIMIT ?
            """, (model_key, limit)).fetchall()
            
            return [DriftCheck(**dict(row)) for row in rows]


class AlertRepository:
    """Repository for alerts"""
    
    def create(self, alert: Alert) -> Alert:
        """Create a new alert"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO alerts (
                    alert_id, type, severity, model_key, message,
                    details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.type, alert.severity,
                alert.model_key, alert.message, alert.details,
                alert.created_at or datetime.now()
            ))
        return alert
    
    def get_active(self) -> List[Alert]:
        """Get all active (non-dismissed) alerts"""
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM alerts 
                WHERE dismissed_at IS NULL 
                ORDER BY created_at DESC
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
    
    def dismiss(self, alert_id: str, dismissed_by: str = "system") -> bool:
        """Dismiss an alert"""
        with db.get_connection() as conn:
            conn.execute("""
                UPDATE alerts 
                SET dismissed_at = ?, dismissed_by = ? 
                WHERE alert_id = ?
            """, (datetime.now(), dismissed_by, alert_id))
            return True


class PredictionLogRepository:
    """Repository for prediction logs (for drift detection)"""
    
    def create(self, log: PredictionLog) -> PredictionLog:
        """Create a new prediction log"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO prediction_logs (
                    log_id, model_key, version, input_features,
                    prediction, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                log.log_id, log.model_key, log.version,
                log.input_features, log.prediction, log.confidence,
                log.created_at or datetime.now()
            ))
        return log
    
    def get_recent_features(
        self, 
        model_key: str, 
        version: str, 
        hours: int = 24,
        limit: int = 10000
    ) -> List[bytes]:
        """Get recent prediction features for drift detection"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT input_features FROM prediction_logs
                WHERE model_key = ? AND version = ? 
                AND created_at >= ?
                AND input_features IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
            """, (model_key, version, cutoff_time, limit)).fetchall()
            
            return [row['input_features'] for row in rows if row['input_features']]
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """Clean up prediction logs older than specified days"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with db.get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM prediction_logs
                WHERE created_at < ?
            """, (cutoff_time,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count


class EventRepository:
    """Repository for events"""
    
    def create(self, event: Event) -> Event:
        """Create a new event"""
        with db.get_connection() as conn:
            conn.execute("""
                INSERT INTO events (
                    event_id, event_type, source, model_key, status, stage,
                    input_data, output_data, user_agent, client_ip,
                    created_at, completed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.event_type, event.source, event.model_key,
                event.status, event.stage, event.input_data, event.output_data,
                event.user_agent, event.client_ip,
                event.created_at or datetime.now(), event.completed_at,
                event.error_message
            ))
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID"""
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM events WHERE event_id = ?
            """, (event_id,)).fetchone()
            
            if row:
                row_dict = dict(row)
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
                    error_message=row_dict.get('error_message')
                )
            return None
    
    def get_all(
        self, 
        limit: int = 50,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> List[Event]:
        """Get all events with optional filters"""
        with db.get_connection() as conn:
            conditions = []
            params = []
            
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if source:
                conditions.append("source = ?")
                params.append(source)
            if status:
                conditions.append("status = ?")
                params.append(status)
            if client_ip:
                conditions.append("client_ip = ?")
                params.append(client_ip)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.append(limit)
            
            rows = conn.execute(f"""
                SELECT * FROM events 
                WHERE {where_clause}
                ORDER BY created_at DESC 
                LIMIT ?
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
                    error_message=row_dict.get('error_message')
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
                    error_message=row_dict.get('error_message')
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
        error_message: Optional[str] = None
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
            
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            conn.execute(f"""
                UPDATE events SET {set_clause} WHERE event_id = ?
            """, list(updates.values()) + [event_id])
            return True


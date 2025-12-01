"""Database migrations"""
from datetime import datetime
from ml_service.db.connection import db


def create_schema():
    """Create database schema"""
    with db.get_connection() as conn:
        # Models table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_key TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                accuracy REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_trained DATETIME,
                last_updated DATETIME,
                task_type TEXT,
                target_field TEXT,
                feature_fields TEXT
            )
        """)
        
        # Jobs table (renamed from training_jobs, supports all job types)
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
                FOREIGN KEY(model_key) REFERENCES models(model_key)
            )
        """)
        
        # Migrate data from training_jobs to jobs if training_jobs exists
        # Check if training_jobs table exists before migrating
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='training_jobs'
        """)
        if cursor.fetchone():
            # Table exists, migrate data
            conn.execute("""
                INSERT OR IGNORE INTO jobs (
                    job_id, model_key, job_type, status, created_at, started_at,
                    completed_at, dataset_size, metrics, error_message
                )
                SELECT 
                    job_id, model_key, 'train', status, created_at, started_at,
                    completed_at, dataset_size, metrics, error_message
                FROM training_jobs
                WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.job_id = training_jobs.job_id)
            """)
            
            # Drop old training_jobs table after migration
            conn.execute("DROP TABLE IF EXISTS training_jobs")
        
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
                UNIQUE(model_key, dataset_version),
                FOREIGN KEY(model_key) REFERENCES models(model_key)
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
                reverted_at DATETIME,
                FOREIGN KEY(model_key) REFERENCES models(model_key)
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
                UNIQUE(model_key, check_date),
                FOREIGN KEY(model_key) REFERENCES models(model_key)
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
                dismissed_by TEXT,
                FOREIGN KEY(model_key) REFERENCES models(model_key)
            )
        """)
        
        # Prediction logs table for drift detection
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prediction_logs (
                log_id TEXT PRIMARY KEY,
                model_key TEXT NOT NULL,
                version TEXT NOT NULL,
                input_features BLOB,
                prediction TEXT,
                confidence REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(model_key) REFERENCES models(model_key)
            )
        """)
        
        # Events table for monitoring all events (drift, predict, train)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                model_key TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT,
                input_data TEXT,
                output_data TEXT,
                user_agent TEXT,
                client_ip TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                error_message TEXT,
                FOREIGN KEY(model_key) REFERENCES models(model_key)
            )
        """)
        
        # Create indexes for faster queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prediction_logs_model_created 
            ON prediction_logs(model_key, created_at)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_client_ip 
            ON events(client_ip)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_user_agent 
            ON events(user_agent)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type_source 
            ON events(event_type, source)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created_at 
            ON events(created_at)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_type_status 
            ON jobs(job_type, status)
        """)
        
        conn.commit()
        print("Database schema created successfully")


def run_migrations():
    """Run all migrations"""
    create_schema()


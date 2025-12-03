"""Database migrations"""
import os
import shutil
import logging
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from ml_service.db.connection import db
from ml_service.core.config import settings

logger = logging.getLogger(__name__)


def create_schema():
    """Create database schema"""
    with db.get_connection() as conn:
        # Users table for authentication
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
        
        # Create system_admin from env if users table is empty
        existing_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        if existing_users and existing_users['count'] == 0:
            from ml_service.core.config import settings
            admin_username = settings.ML_ADMIN_USERNAME
            admin_password = settings.ML_ADMIN_PASSWORD
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            conn.execute("""
                INSERT INTO users (user_id, username, password_hash, tier)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), admin_username, password_hash, 'system_admin'))
            logger.info(f"Created system_admin user ({admin_username})")
        
        # API tokens table (for sessions and API keys)
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
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        
        # Create indexes for api_tokens
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id, token_type)
        """)
        
        # Models table - composite PRIMARY KEY (model_key, version) to support multiple versions
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


def migrate_v3_2_fields():
    """Migrate database to v3.2 - add new fields to jobs and events tables, fix models PRIMARY KEY"""
    with db.get_connection() as conn:
        # Helper function to check if column exists
        def column_exists(table_name: str, column_name: str) -> bool:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        
        # Migrate models table to support composite PRIMARY KEY (model_key, version)
        # This allows multiple versions of the same model
        try:
            # Check if models table has old PRIMARY KEY structure
            cursor = conn.execute("PRAGMA table_info(models)")
            columns = {row[1]: row for row in cursor.fetchall()}
            
            # Check if PRIMARY KEY is on model_key only (old structure)
            # SQLite doesn't expose PRIMARY KEY info directly, so we check by trying to insert duplicate
            # Instead, we'll check if we can query by both model_key and version
            # If the table was created with old schema, we need to migrate it
            
            # Check if table exists and has data
            table_check = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='models'
            """).fetchone()
            
            if table_check:
                # Check if we need to migrate (if PRIMARY KEY is only on model_key)
                # We'll recreate the table with composite PRIMARY KEY
                # First, backup existing data
                existing_models = conn.execute("SELECT * FROM models").fetchall()
                
                if existing_models:
                    # Check if we can have multiple versions (test by checking constraint)
                    # If we can't, we need to migrate
                    try:
                        # Try to create a test entry with same model_key but different version
                        # This will fail if PRIMARY KEY is only on model_key
                        test_key = "___MIGRATION_TEST___"
                        test_version1 = "v1.0.0"
                        test_version2 = "v2.0.0"
                        
                        # Clean up any test entries first
                        conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                        
                        # Try inserting two entries with same model_key but different versions
                        conn.execute("""
                            INSERT INTO models (model_key, version, status) 
                            VALUES (?, ?, 'active')
                        """, (test_key, test_version1))
                        
                        try:
                            conn.execute("""
                                INSERT INTO models (model_key, version, status) 
                                VALUES (?, ?, 'active')
                            """, (test_key, test_version2))
                            # If we get here, composite PRIMARY KEY already exists
                            conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                            logger.info("Models table already has composite PRIMARY KEY")
                        except Exception:
                            # Can't insert - need to migrate
                            conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                            logger.info("Migrating models table to composite PRIMARY KEY...")
                            
                            # Create new table with composite PRIMARY KEY
                            conn.execute("""
                                CREATE TABLE models_new (
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
                            
                            # Copy data from old table (use version from existing or default to 'v1.0.0')
                            for row in existing_models:
                                model_key = row['model_key']
                                version = row.get('version') or 'v1.0.0'
                                # If version is missing, use default
                                conn.execute("""
                                    INSERT INTO models_new (
                                        model_key, version, status, accuracy, created_at,
                                        last_trained, last_updated, task_type, target_field, feature_fields
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    model_key, version, row.get('status', 'active'),
                                    row.get('accuracy'), row.get('created_at'),
                                    row.get('last_trained'), row.get('last_updated'),
                                    row.get('task_type'), row.get('target_field'), row.get('feature_fields')
                                ))
                            
                            # Drop old table and rename new one
                            conn.execute("DROP TABLE models")
                            conn.execute("ALTER TABLE models_new RENAME TO models")
                            logger.info("Models table migrated to composite PRIMARY KEY")
                    except Exception as e:
                        logger.warning(f"Could not test models table structure: {e}")
        except Exception as e:
            logger.warning(f"Error migrating models table: {e}")
        
        # Add new columns to jobs table
        jobs_new_columns = [
            ("priority", "INTEGER DEFAULT 5"),
            ("user_tier", "TEXT DEFAULT 'user'"),
            ("user_id", "TEXT"),
            ("data_size_bytes", "INTEGER"),
            ("progress_current", "INTEGER DEFAULT 0"),
            ("progress_total", "INTEGER DEFAULT 100"),
            ("model_version", "TEXT"),
            ("assigned_worker_id", "TEXT"),
            ("request_payload", "TEXT"),
            ("result_payload", "TEXT"),
            ("user_os", "TEXT"),
            ("user_device", "TEXT"),
            ("user_cpu_cores", "INTEGER"),
            ("user_ram_gb", "REAL"),
            ("user_gpu", "TEXT"),
        ]
        
        for column_name, column_def in jobs_new_columns:
            if not column_exists("jobs", column_name):
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_def}")
                    print(f"Added column {column_name} to jobs table")
                except Exception as e:
                    print(f"Error adding column {column_name} to jobs: {e}")
        
        # Add new columns to events table
        events_new_columns = [
            ("duration_ms", "INTEGER"),
            ("display_format", "TEXT DEFAULT 'table'"),
            ("data_size_bytes", "INTEGER"),
        ]
        
        for column_name, column_def in events_new_columns:
            if not column_exists("events", column_name):
                try:
                    conn.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_def}")
                    print(f"Added column {column_name} to events table")
                except Exception as e:
                    print(f"Error adding column {column_name} to events: {e}")
        
        # Create new indexes for jobs table
        indexes = [
            ("idx_jobs_status_created", "jobs(status, created_at)"),
            ("idx_jobs_priority_created", "jobs(priority, created_at)"),
            ("idx_jobs_model_key", "jobs(model_key)"),
            ("idx_jobs_user", "jobs(user_id)"),
        ]
        
        for index_name, index_def in indexes:
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
                print(f"Created index {index_name}")
            except Exception as e:
                print(f"Error creating index {index_name}: {e}")
        
        conn.commit()
        print("v3.2 migration completed successfully")


def recreate_database(backup: bool = True, restore_from_backup: bool = False) -> dict:
    """
    Recreate database with clean schema.
    
    Args:
        backup: If True, create backup of current database before deletion
        restore_from_backup: If True, restore data from backup after recreation
    
    Returns:
        dict with status and backup path if created
    """
    db_path = Path(settings.ML_DB_PATH)
    backup_path = None
    
    try:
        # Step 1: Create backup if requested and database exists
        if backup and db_path.exists():
            backup_path = db_path.parent / f"{db_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        # Step 2: Delete old database file
        # Note: SQLite will handle closing connections when file is deleted
        if db_path.exists():
            # Delete database file (SQLite will close connections automatically)
            os.remove(db_path)
            logger.info(f"Deleted old database: {db_path}")
        
        # Step 3: Recreate database with clean schema
        create_schema()
        migrate_v3_2_fields()
        logger.info("Database recreated successfully")
        
        # Step 4: Optionally restore data from backup
        if restore_from_backup and backup_path and backup_path.exists():
            # Copy backup file back and reapply migrations
            shutil.copy2(backup_path, db_path)
            logger.info(f"Restored data from backup: {backup_path}")
            # Reapply migrations to ensure schema is up to date
            migrate_v3_2_fields()
            logger.info("Migrations reapplied after restore")
        
        return {
            "status": "success",
            "backup_created": backup_path is not None,
            "backup_path": str(backup_path) if backup_path else None,
            "database_recreated": True
        }
        
    except Exception as e:
        logger.error(f"Error recreating database: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "backup_path": str(backup_path) if backup_path else None
        }


def run_migrations():
    """Run all migrations"""
    create_schema()
    migrate_v3_2_fields()


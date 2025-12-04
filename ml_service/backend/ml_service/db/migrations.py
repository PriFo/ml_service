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


def _get_legacy_db_connection():
    """Get connection to legacy database (only for migration purposes)"""
    import sqlite3
    legacy_db_path = Path(settings.ML_DB_PATH)
    if not legacy_db_path.exists():
        return None
    conn = sqlite3.connect(
        str(legacy_db_path),
        timeout=settings.ML_DB_TIMEOUT,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def create_schema():
    """
    DEPRECATED: This function creates schema in legacy database.
    Use create_schemas_for_separated_databases() instead.
    This function is kept only for backward compatibility.
    """
    logger.warning("create_schema() is deprecated. Use create_schemas_for_separated_databases() instead.")
    legacy_conn = _get_legacy_db_connection()
    if not legacy_conn:
        logger.warning("Legacy database not found, skipping create_schema()")
        return
    try:
        # Users table for authentication
        legacy_conn.execute("""
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
        existing_users = legacy_conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        if existing_users and existing_users['count'] == 0:
            from ml_service.core.config import settings
            admin_username = settings.ML_ADMIN_USERNAME
            admin_password = settings.ML_ADMIN_PASSWORD
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            legacy_conn.execute("""
                INSERT INTO users (user_id, username, password_hash, tier)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), admin_username, password_hash, 'system_admin'))
            logger.info(f"Created system_admin user ({admin_username})")
        
        # API tokens table (for sessions and API keys)
        legacy_conn.execute("""
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
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)
        """)
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id, token_type)
        """)
        
        # Models table - composite PRIMARY KEY (model_key, version) to support multiple versions
        legacy_conn.execute("""
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
        legacy_conn.execute("""
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
        cursor = legacy_conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='training_jobs'
        """)
        if cursor.fetchone():
            # Table exists, migrate data
            legacy_conn.execute("""
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
            legacy_conn.execute("DROP TABLE IF EXISTS training_jobs")
        
        # Client datasets table
        legacy_conn.execute("""
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
        legacy_conn.execute("""
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
        legacy_conn.execute("""
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
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prediction_logs_model_created 
            ON prediction_logs(model_key, created_at)
        """)
        
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_client_ip 
            ON events(client_ip)
        """)
        
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_user_agent 
            ON events(user_agent)
        """)
        
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type_source 
            ON events(event_type, source)
        """)
        
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created_at 
            ON events(created_at)
        """)
        
        legacy_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_type_status 
            ON jobs(job_type, status)
        """)
        
        legacy_conn.commit()
        print("Database schema created successfully (legacy database)")
    finally:
        legacy_conn.close()


def migrate_v3_2_fields():
    """
    DEPRECATED: This function migrates legacy database.
    Use create_schemas_for_separated_databases() instead.
    This function is kept only for backward compatibility.
    """
    logger.warning("migrate_v3_2_fields() is deprecated. Use create_schemas_for_separated_databases() instead.")
    legacy_conn = _get_legacy_db_connection()
    if not legacy_conn:
        logger.warning("Legacy database not found, skipping migrate_v3_2_fields()")
        return
    try:
        # Helper function to check if column exists
        def column_exists(table_name: str, column_name: str) -> bool:
            cursor = legacy_conn.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            return column_name in columns
        
        # Migrate models table to support composite PRIMARY KEY (model_key, version)
        # This allows multiple versions of the same model
        try:
            # Check if models table has old PRIMARY KEY structure
            cursor = legacy_conn.execute("PRAGMA table_info(models)")
            columns = {row[1]: row for row in cursor.fetchall()}
            
            # Check if PRIMARY KEY is on model_key only (old structure)
            # SQLite doesn't expose PRIMARY KEY info directly, so we check by trying to insert duplicate
            # Instead, we'll check if we can query by both model_key and version
            # If the table was created with old schema, we need to migrate it
            
            # Check if table exists and has data
            table_check = legacy_conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='models'
            """).fetchone()
            
            if table_check:
                # Check if we need to migrate (if PRIMARY KEY is only on model_key)
                # We'll recreate the table with composite PRIMARY KEY
                # First, backup existing data
                existing_models = legacy_conn.execute("SELECT * FROM models").fetchall()
                
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
                        legacy_conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                        
                        # Try inserting two entries with same model_key but different versions
                        legacy_conn.execute("""
                            INSERT INTO models (model_key, version, status) 
                            VALUES (?, ?, 'active')
                        """, (test_key, test_version1))
                        
                        try:
                            legacy_conn.execute("""
                                INSERT INTO models (model_key, version, status) 
                                VALUES (?, ?, 'active')
                            """, (test_key, test_version2))
                            # If we get here, composite PRIMARY KEY already exists
                            legacy_conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                            logger.info("Models table already has composite PRIMARY KEY")
                        except Exception:
                            # Can't insert - need to migrate
                            legacy_conn.execute("DELETE FROM models WHERE model_key = ?", (test_key,))
                            logger.info("Migrating models table to composite PRIMARY KEY...")
                            
                            # Create new table with composite PRIMARY KEY
                            legacy_conn.execute("""
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
                                legacy_conn.execute("""
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
                            legacy_conn.execute("DROP TABLE models")
                            legacy_conn.execute("ALTER TABLE models_new RENAME TO models")
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
                    legacy_conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_def}")
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
                    legacy_conn.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_def}")
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
                legacy_conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
                print(f"Created index {index_name}")
            except Exception as e:
                print(f"Error creating index {index_name}: {e}")
        
        legacy_conn.commit()
        print("v3.2 migration completed successfully (legacy database)")
    finally:
        legacy_conn.close()


def recreate_database(backup: bool = True, restore_from_backup: bool = False) -> dict:
    """
    DEPRECATED: Recreate legacy database with clean schema.
    This function is kept for backward compatibility but should not be used.
    Use create_schemas_for_separated_databases() to recreate separated databases.
    
    Args:
        backup: If True, create backup of current database before deletion
        restore_from_backup: If True, restore data from backup after recreation
    
    Returns:
        dict with status and backup path if created
    """
    logger.warning("recreate_database() is deprecated. Use create_schemas_for_separated_databases() instead.")
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
        
        # Step 3: Recreate database with clean schema (legacy)
        create_schema()
        migrate_v3_2_fields()
        logger.info("Legacy database recreated successfully")
        
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
            "database_recreated": True,
            "warning": "This function recreates legacy database. Use separated databases instead."
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
                prediction TEXT,
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
        
        conn.commit()
        logger.info("Logs database schema created")
    
    logger.info("All separated database schemas created successfully")


def migrate_to_separated_databases() -> dict:
    """
    Migrate data from legacy single database to separated databases.
    
    Returns:
        dict with migration status and statistics
    """
    legacy_db_path = Path(settings.ML_DB_PATH)
    
    if not legacy_db_path.exists():
        logger.info("Legacy database does not exist, skipping migration")
        return {
            "status": "skipped",
            "reason": "Legacy database not found"
        }
    
    logger.info("Starting migration to separated databases...")
    
    # Create backup
    backup_path = legacy_db_path.parent / f"{legacy_db_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(legacy_db_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Create schemas for new databases
    create_schemas_for_separated_databases()
    
    stats = {
        "users": 0,
        "api_tokens": 0,
        "models": 0,
        "jobs": 0,
        "client_datasets": 0,
        "retraining_jobs": 0,
        "drift_checks": 0,
        "alerts": 0,
        "prediction_logs": 0,
        "events": 0
    }
    
    try:
        # Read from legacy database (direct connection, not through db_manager)
        legacy_conn = _get_legacy_db_connection()
        if not legacy_conn:
            logger.warning("Legacy database not found, nothing to migrate")
            return {
                "status": "skipped",
                "reason": "Legacy database not found"
            }
        
        try:
            # Migrate users
            users = legacy_conn.execute("SELECT * FROM users").fetchall()
            if users:
                with db_manager.users_db.get_connection() as users_conn:
                    for user in users:
                        users_conn.execute("""
                            INSERT OR IGNORE INTO users 
                            (user_id, username, password_hash, tier, created_at, last_login, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            user['user_id'], user['username'], user['password_hash'],
                            user['tier'], user.get('created_at'), user.get('last_login'),
                            user.get('is_active', 1)
                        ))
                    users_conn.commit()
                    stats["users"] = len(users)
                    logger.info(f"Migrated {len(users)} users")
            
            # Migrate API tokens
            api_tokens = legacy_conn.execute("SELECT * FROM api_tokens").fetchall()
            if api_tokens:
                with db_manager.users_db.get_connection() as users_conn:
                    for token in api_tokens:
                        users_conn.execute("""
                            INSERT OR IGNORE INTO api_tokens
                            (token_id, token_hash, user_id, token_type, name, created_at, expires_at, last_used_at, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            token['token_id'], token['token_hash'], token['user_id'],
                            token['token_type'], token.get('name'), token.get('created_at'),
                            token.get('expires_at'), token.get('last_used_at'), token.get('is_active', 1)
                        ))
                    users_conn.commit()
                    stats["api_tokens"] = len(api_tokens)
                    logger.info(f"Migrated {len(api_tokens)} API tokens")
            
            # Migrate models
            models = legacy_conn.execute("SELECT * FROM models").fetchall()
            if models:
                with db_manager.models_db.get_connection() as models_conn:
                    for model in models:
                        models_conn.execute("""
                            INSERT OR IGNORE INTO models
                            (model_key, version, status, accuracy, created_at, last_trained, last_updated, task_type, target_field, feature_fields)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            model['model_key'], model.get('version', 'v1.0.0'), model.get('status', 'active'),
                            model.get('accuracy'), model.get('created_at'), model.get('last_trained'),
                            model.get('last_updated'), model.get('task_type'), model.get('target_field'),
                            model.get('feature_fields')
                        ))
                    models_conn.commit()
                    stats["models"] = len(models)
                    logger.info(f"Migrated {len(models)} models")
            
            # Migrate jobs
            jobs = legacy_conn.execute("SELECT * FROM jobs").fetchall()
            if jobs:
                with db_manager.models_db.get_connection() as models_conn:
                    for job in jobs:
                        # Get all columns dynamically
                        columns = [col for col in job.keys()]
                        placeholders = ','.join(['?' for _ in columns])
                        columns_str = ','.join(columns)
                        values = [job[col] for col in columns]
                        models_conn.execute(f"""
                            INSERT OR IGNORE INTO jobs ({columns_str})
                            VALUES ({placeholders})
                        """, values)
                    models_conn.commit()
                    stats["jobs"] = len(jobs)
                    logger.info(f"Migrated {len(jobs)} jobs")
            
            # Migrate other model-related tables
            for table in ['client_datasets', 'retraining_jobs', 'drift_checks', 'alerts', 'prediction_logs']:
                try:
                    rows = legacy_conn.execute(f"SELECT * FROM {table}").fetchall()
                    if rows:
                        with db_manager.models_db.get_connection() as models_conn:
                            for row in rows:
                                columns = [col for col in row.keys()]
                                placeholders = ','.join(['?' for _ in columns])
                                columns_str = ','.join(columns)
                                values = [row[col] for col in columns]
                                models_conn.execute(f"""
                                    INSERT OR IGNORE INTO {table} ({columns_str})
                                    VALUES ({placeholders})
                                """, values)
                            models_conn.commit()
                            stats[table] = len(rows)
                            logger.info(f"Migrated {len(rows)} {table}")
                except Exception as e:
                    logger.warning(f"Could not migrate {table}: {e}")
            
            # Migrate events to specialized tables
            events = legacy_conn.execute("SELECT * FROM events").fetchall()
            if events:
                event_type_mapping = {
                    'alert': 'alert_events',
                    'train': 'train_events',
                    'predict': 'predict_events',
                    'login': 'login_events',
                    'system': 'system_events',
                    'drift': 'drift_events',
                    'job': 'job_events'
                }
                
                with db_manager.logs_db.get_connection() as logs_conn:
                    for event in events:
                        event_type = event.get('event_type', '').lower()
                        target_table = None
                        
                        # Determine target table based on event_type or source
                        if 'alert' in event_type:
                            target_table = 'alert_events'
                        elif 'train' in event_type or event.get('source') == 'training':
                            target_table = 'train_events'
                        elif 'predict' in event_type or event.get('source') == 'prediction':
                            target_table = 'predict_events'
                        elif 'login' in event_type or event.get('source') == 'auth':
                            target_table = 'login_events'
                        elif 'system' in event_type or event.get('source') == 'system':
                            target_table = 'system_events'
                        elif 'drift' in event_type:
                            target_table = 'drift_events'
                        elif 'job' in event_type:
                            target_table = 'job_events'
                        else:
                            # Default to system_events for unknown types
                            target_table = 'system_events'
                        
                        # Insert into appropriate table
                        try:
                            if target_table == 'alert_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO alert_events
                                    (event_id, event_type, model_key, message, details, created_at, client_ip, user_agent)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], event.get('event_type', 'alert'),
                                    event.get('model_key'), event.get('input_data', ''),
                                    event.get('output_data'), event.get('created_at'),
                                    event.get('client_ip'), event.get('user_agent')
                                ))
                            elif target_table == 'train_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO train_events
                                    (event_id, model_key, version, job_id, status, stage, metrics, error_message, created_at, completed_at, duration_ms, data_size_bytes)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], event.get('model_key'), None,
                                    None, event.get('status', 'queued'), event.get('stage'),
                                    event.get('output_data'), event.get('error_message'),
                                    event.get('created_at'), event.get('completed_at'),
                                    event.get('duration_ms'), event.get('data_size_bytes')
                                ))
                            elif target_table == 'predict_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO predict_events
                                    (event_id, model_key, version, job_id, status, error_message, created_at, completed_at, duration_ms, data_size_bytes, client_ip, user_agent)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], event.get('model_key'), None,
                                    None, event.get('status', 'queued'), event.get('error_message'),
                                    event.get('created_at'), event.get('completed_at'),
                                    event.get('duration_ms'), event.get('data_size_bytes'),
                                    event.get('client_ip'), event.get('user_agent')
                                ))
                            elif target_table == 'login_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO login_events
                                    (event_id, user_id, username, event_type, ip_address, user_agent, success, error_message, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], None, None,
                                    event.get('event_type', 'login'), event.get('client_ip'),
                                    event.get('user_agent'), 1, event.get('error_message'),
                                    event.get('created_at')
                                ))
                            elif target_table == 'system_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO system_events
                                    (event_id, event_type, component, message, severity, details, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], event.get('event_type', 'system'),
                                    event.get('source', 'system'), event.get('input_data', ''),
                                    'info', event.get('output_data'), event.get('created_at')
                                ))
                            elif target_table == 'drift_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO drift_events
                                    (event_id, model_key, check_id, drift_detected, created_at)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], event.get('model_key'), None,
                                    0, event.get('created_at')
                                ))
                            elif target_table == 'job_events':
                                logs_conn.execute("""
                                    INSERT OR IGNORE INTO job_events
                                    (event_id, job_id, job_type, model_key, status, stage, created_at, completed_at, error_message)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    event['event_id'], None, event.get('event_type', 'job'),
                                    event.get('model_key'), event.get('status', 'queued'),
                                    event.get('stage'), event.get('created_at'),
                                    event.get('completed_at'), event.get('error_message')
                                ))
                        except Exception as e:
                            logger.warning(f"Error migrating event {event.get('event_id')} to {target_table}: {e}")
                    
                    logs_conn.commit()
                    stats["events"] = len(events)
                    logger.info(f"Migrated {len(events)} events to specialized tables")
        
            logger.info("Migration completed successfully")
            return {
                "status": "success",
                "backup_path": str(backup_path),
                "statistics": stats
            }
        finally:
            legacy_conn.close()
    
    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "backup_path": str(backup_path),
            "statistics": stats
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


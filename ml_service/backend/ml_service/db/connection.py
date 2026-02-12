"""Database connection management with separated databases and queue-based writes"""
import sqlite3
import threading
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict, Any
from enum import Enum

from ml_service.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseStatus(Enum):
    """Database connection status"""
    ONLINE = "online"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"
    RESTARTING = "restarting"
    LOCKED = "locked"
    ERROR = "error"


class BaseDatabase:
    """Base class for database connections with mutex protection"""
    
    def __init__(self, db_path: str, db_name: str):
        self.db_path = db_path
        self.db_name = db_name
        self._write_lock = threading.Lock()  # Mutex for write operations
        self._status = DatabaseStatus.OFFLINE
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection for reading (no mutex needed)"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=settings.ML_DB_TIMEOUT,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            try:
                # Configure connection for optimal performance
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA foreign_keys = ON")
                busy_timeout_ms = settings.ML_DB_TIMEOUT * 1000
                conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
                self._status = DatabaseStatus.ONLINE
                yield conn
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                self._status = DatabaseStatus.LOCKED
            else:
                self._status = DatabaseStatus.OFFLINE
            raise
        except Exception as e:
            logger.error(f"Error connecting to {self.db_name}: {e}")
            self._status = DatabaseStatus.OFFLINE
            raise
    
    def execute_write(self, operation: callable, *args, **kwargs) -> Any:
        """Execute write operation with mutex protection"""
        with self._write_lock:
            try:
                self._status = DatabaseStatus.ONLINE
                conn = sqlite3.connect(
                    self.db_path,
                    timeout=settings.ML_DB_TIMEOUT,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                try:
                    # Configure connection for optimal performance
                    conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    conn.execute("PRAGMA foreign_keys = ON")
                    busy_timeout_ms = settings.ML_DB_TIMEOUT * 1000
                    conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
                    
                    result = operation(conn)
                    conn.commit()
                    return result
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    logger.warning(f"Database {self.db_name} is locked, operation will be retried")
                    self._status = DatabaseStatus.LOCKED
                    raise
                else:
                    logger.error(f"Database {self.db_name} error: {e}")
                    self._status = DatabaseStatus.ERROR
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in database {self.db_name}: {e}")
                self._status = DatabaseStatus.ERROR
                raise
    
    def queue_write(self, operation, table: str, data: Any, callback: Optional[callable] = None):
        """Queue write operation (to be implemented by queue manager)"""
        # This will be handled by WriteQueueManager
        from ml_service.db.queue_manager import WriteOperation
        # Get global queue manager instance (will be initialized in app.py)
        try:
            from ml_service.db import queue_manager_instance
            if queue_manager_instance and queue_manager_instance.running:
                # operation can be WriteOperation enum or string
                if isinstance(operation, str):
                    op = WriteOperation[operation.upper()] if hasattr(WriteOperation, operation.upper()) else WriteOperation.CUSTOM
                else:
                    op = operation
                return queue_manager_instance.queue_write(self.db_name, op, table, data, callback)
        except (ImportError, AttributeError, KeyError) as e:
            # Fallback to direct execution if queue manager not available
            logger.warning(f"Queue manager not available, executing write directly for {self.db_name}.{table}: {e}")
            if isinstance(data, dict) and "sql" in data and "params" in data:
                return self.execute_write(lambda conn: conn.execute(data["sql"], data["params"]))
            return None
    
    def _direct_write(self, conn, operation: str, table: str, data: Any):
        """Direct write execution (fallback)"""
        if isinstance(data, dict) and "sql" in data and "params" in data:
            cursor = conn.execute(data["sql"], data["params"])
            return cursor.lastrowid if operation == "create" else cursor.rowcount
        raise NotImplementedError(f"Direct write for {operation} on {table} not implemented")
    
    def health_check(self) -> bool:
        """Check if database is accessible (non-blocking)"""
        try:
            # Use a short timeout for health check to avoid blocking
            conn = sqlite3.connect(
                self.db_path,
                timeout=1,  # Short timeout for health check
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("SELECT 1")
                self._status = DatabaseStatus.ONLINE
                return True
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                logger.warning(f"Health check: Database {self.db_name} is locked")
                self._status = DatabaseStatus.LOCKED
            else:
                logger.warning(f"Health check failed for {self.db_name}: {e}")
                self._status = DatabaseStatus.OFFLINE
            return False
        except Exception as e:
            logger.warning(f"Health check failed for {self.db_name}: {e}")
            self._status = DatabaseStatus.OFFLINE
            return False
    
    def reconnect(self) -> bool:
        """Attempt to reconnect to database (non-blocking)"""
        # Don't block on reconnect - try to acquire lock with timeout
        if not self._write_lock.acquire(timeout=0.1):
            # If lock is held, set status to RESTARTING and return False
            # The actual reconnect will happen in background thread
            self._status = DatabaseStatus.RESTARTING
            logger.warning(f"Cannot reconnect {self.db_name} - lock is held, will retry in background")
            return False
        
        try:
            self._status = DatabaseStatus.RECONNECTING
            # Close any existing connections by attempting a simple query
            try:
                with self.get_connection() as conn:
                    conn.execute("SELECT 1")
                self._status = DatabaseStatus.ONLINE
                logger.info(f"Successfully reconnected to {self.db_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect to {self.db_name}: {e}")
                self._status = DatabaseStatus.ERROR
                return False
        finally:
            self._write_lock.release()
    
    @property
    def status(self) -> DatabaseStatus:
        """Get current database status"""
        return self._status


class ModelsDatabase(BaseDatabase):
    """Database for models, jobs, and related data"""
    
    def __init__(self):
        super().__init__(settings.ML_DB_MODELS_PATH, "models")


class UsersDatabase(BaseDatabase):
    """Database for users and authentication"""
    
    def __init__(self):
        super().__init__(settings.ML_DB_USERS_PATH, "users")


class LogsDatabase(BaseDatabase):
    """Database for system logs and events"""
    
    def __init__(self):
        super().__init__(settings.ML_DB_LOGS_PATH, "logs")


class DatabaseManager:
    """Manager for all database connections"""
    
    def __init__(self):
        self.models_db = ModelsDatabase()
        self.users_db = UsersDatabase()
        self.logs_db = LogsDatabase()
        self._manager_lock = threading.Lock()  # Mutex for manager state
        self._db_status: Dict[str, DatabaseStatus] = {
            "models": DatabaseStatus.OFFLINE,
            "users": DatabaseStatus.OFFLINE,
            "logs": DatabaseStatus.OFFLINE
        }
    
    def check_all_databases(self) -> Dict[str, bool]:
        """Check health of all databases"""
        with self._manager_lock:
            results = {}
            for db_name, db in [("models", self.models_db), ("users", self.users_db), ("logs", self.logs_db)]:
                is_healthy = db.health_check()
                results[db_name] = is_healthy
                self._db_status[db_name] = db.status
            return results
    
    def reconnect_database(self, db_name: str) -> bool:
        """Reconnect to a specific database (non-blocking)"""
        # Don't block on reconnect - try to acquire lock with timeout
        if not self._manager_lock.acquire(timeout=0.1):
            # If lock is held, start reconnect in background thread
            import threading
            db = self._get_database(db_name)
            if db:
                db._status = DatabaseStatus.RESTARTING
                reconnect_thread = threading.Thread(
                    target=self._reconnect_in_background,
                    args=(db_name,),
                    name=f"Reconnect-{db_name}",
                    daemon=True
                )
                reconnect_thread.start()
                return False  # Reconnect started in background
            return False
        
        try:
            db = self._get_database(db_name)
            if db:
                success = db.reconnect()
                self._db_status[db_name] = db.status
                return success
            return False
        finally:
            self._manager_lock.release()
    
    def _reconnect_in_background(self, db_name: str):
        """Reconnect database in background thread"""
        db = self._get_database(db_name)
        if db:
            try:
                db.reconnect()
                with self._manager_lock:
                    self._db_status[db_name] = db.status
            except Exception as e:
                logger.error(f"Background reconnect failed for {db_name}: {e}")
                with self._manager_lock:
                    self._db_status[db_name] = DatabaseStatus.ERROR
    
    def _get_database(self, db_name: str) -> Optional[BaseDatabase]:
        """Get database instance by name"""
        if db_name == "models":
            return self.models_db
        elif db_name == "users":
            return self.users_db
        elif db_name == "logs":
            return self.logs_db
        return None
    
    def get_database_status(self) -> Dict[str, str]:
        """Get status of all databases"""
        with self._manager_lock:
            return {name: status.value for name, status in self._db_status.items()}


# Global database manager instance
db_manager = DatabaseManager()

# DEPRECATED: Legacy support - kept only for migration purposes
class DatabaseConnection:
    """
    DEPRECATED: This class is no longer supported.
    Use db_manager.models_db, db_manager.users_db, or db_manager.logs_db instead.
    """
    
    def __init__(self, db_path: str = None):
        import warnings
        warnings.warn(
            "DatabaseConnection is deprecated and no longer supported. Use db_manager.models_db, db_manager.users_db, or db_manager.logs_db instead.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError("DatabaseConnection is no longer supported. Use db_manager.models_db, db_manager.users_db, or db_manager.logs_db instead.")
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with context manager"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=settings.ML_DB_TIMEOUT,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
            busy_timeout_ms = settings.ML_DB_TIMEOUT * 1000
            conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query"""
        with self.get_connection() as conn:
            return conn.execute(query, params)
    
    def execute_many(self, query: str, params_list: list) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets"""
        with self.get_connection() as conn:
            return conn.executemany(query, params_list)


# DEPRECATED: Legacy global instance removed
# Use db_manager.models_db, db_manager.users_db, or db_manager.logs_db instead
# db = DatabaseConnection()  # No longer supported

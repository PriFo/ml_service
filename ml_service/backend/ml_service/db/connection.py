"""Database connection management"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ml_service.core.config import settings


class DatabaseConnection:
    """SQLite database connection manager"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.ML_DB_PATH
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database with schema"""
        with self.get_connection() as conn:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.commit()
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with context manager"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=settings.ML_DB_TIMEOUT,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
        try:
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


# Global database instance
db = DatabaseConnection()


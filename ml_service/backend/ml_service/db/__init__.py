"""Database components"""
from ml_service.db.connection import (
    DatabaseManager,
    db_manager,
    ModelsDatabase,
    UsersDatabase,
    LogsDatabase,
    BaseDatabase,
    DatabaseStatus,
    db  # DEPRECATED: Legacy support only
)
from ml_service.db.queue_manager import (
    WriteQueueManager,
    WriteOperation,
    QueuedWrite
)

# Global queue manager instance (initialized in app.py)
queue_manager_instance: WriteQueueManager = None

__all__ = [
    'DatabaseManager',
    'db_manager',
    'ModelsDatabase',
    'UsersDatabase',
    'LogsDatabase',
    'BaseDatabase',
    'DatabaseStatus',
    'WriteQueueManager',
    'WriteOperation',
    'QueuedWrite',
    'queue_manager_instance',
    'db'  # DEPRECATED: Use db_manager instead
]

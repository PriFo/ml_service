"""Write queue manager for sequential database write operations"""
import queue
import threading
import logging
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from ml_service.core.config import settings
from ml_service.db.connection import DatabaseManager, BaseDatabase, DatabaseStatus

logger = logging.getLogger(__name__)


class WriteOperation(Enum):
    """Types of write operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CUSTOM = "custom"


@dataclass
class QueuedWrite:
    """Represents a queued write operation"""
    operation: WriteOperation
    table: str
    data: Any
    callback: Optional[Callable] = None
    retry_count: int = 0
    max_retries: int = 3
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class WriteQueueManager:
    """Manages write queues for all databases with worker threads"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.queues: Dict[str, queue.Queue] = {
            "models": queue.Queue(maxsize=settings.ML_DB_QUEUE_MAX_SIZE),
            "users": queue.Queue(maxsize=settings.ML_DB_QUEUE_MAX_SIZE),
            "logs": queue.Queue(maxsize=settings.ML_DB_QUEUE_MAX_SIZE)
        }
        self.workers: Dict[str, threading.Thread] = {}
        self.running = False
        self._stop_event = threading.Event()
    
    def start(self):
        """Start worker threads for all databases"""
        if self.running:
            logger.warning("WriteQueueManager is already running")
            return
        
        self.running = True
        self._stop_event.clear()
        
        # Start worker thread for each database
        for db_name in ["models", "users", "logs"]:
            worker = threading.Thread(
                target=self._worker_loop,
                args=(db_name,),
                name=f"DBWriter-{db_name}",
                daemon=True
            )
            worker.start()
            self.workers[db_name] = worker
            logger.info(f"Started write worker thread for {db_name} database")
    
    def stop(self):
        """Stop all worker threads"""
        if not self.running:
            return
        
        self.running = False
        self._stop_event.set()
        
        # Wait for all workers to finish
        for db_name, worker in self.workers.items():
            # Put sentinel value to wake up worker
            try:
                self.queues[db_name].put(None, timeout=1)
            except queue.Full:
                pass
            worker.join(timeout=5)
            if worker.is_alive():
                logger.warning(f"Worker thread for {db_name} did not stop gracefully")
        
        logger.info("WriteQueueManager stopped")
    
    def queue_write(
        self,
        db_name: str,
        operation: WriteOperation,
        table: str,
        data: Any,
        callback: Optional[Callable] = None
    ) -> bool:
        """Add write operation to queue"""
        if db_name not in self.queues:
            logger.error(f"Unknown database: {db_name}")
            return False
        
        queued_write = QueuedWrite(
            operation=operation,
            table=table,
            data=data,
            callback=callback
        )
        
        try:
            self.queues[db_name].put(queued_write, timeout=1)
            logger.debug(f"Queued {operation.value} operation for {db_name}.{table}")
            return True
        except queue.Full:
            logger.error(f"Write queue for {db_name} is full")
            return False
    
    def _worker_loop(self, db_name: str):
        """Worker thread loop for processing write operations"""
        db = self._get_database(db_name)
        if not db:
            logger.error(f"Database {db_name} not found")
            return
        
        logger.info(f"Write worker for {db_name} started")
        
        while self.running and not self._stop_event.is_set():
            try:
                # Get operation from queue with timeout
                try:
                    queued_write = self.queues[db_name].get(timeout=1)
                except queue.Empty:
                    continue
                
                # Check for sentinel value (stop signal)
                if queued_write is None:
                    break
                
                # Process the write operation
                self._process_write(db, db_name, queued_write)
                
            except Exception as e:
                logger.error(f"Error in worker loop for {db_name}: {e}", exc_info=True)
        
        logger.info(f"Write worker for {db_name} stopped")
    
    def _process_write(self, db: BaseDatabase, db_name: str, queued_write: QueuedWrite):
        """Process a single write operation"""
        try:
            # Execute write operation with mutex protection
            # execute_write expects a callable that takes conn as first argument
            def execute_op(conn):
                return self._execute_operation(conn, queued_write.operation, queued_write.table, queued_write.data)
            
            result = db.execute_write(execute_op)
            
            # Call callback if provided
            if queued_write.callback:
                try:
                    queued_write.callback(result)
                except Exception as e:
                    logger.error(f"Callback error for {db_name}.{queued_write.table}: {e}")
            
            logger.debug(f"Successfully processed {queued_write.operation.value} for {db_name}.{queued_write.table}")
            
        except Exception as e:
            logger.error(f"Error processing write for {db_name}.{queued_write.table}: {e}")
            
            # Retry logic
            if queued_write.retry_count < queued_write.max_retries:
                queued_write.retry_count += 1
                # Exponential backoff
                delay = min(2 ** queued_write.retry_count, settings.ML_DB_RECONNECT_DELAY)
                logger.info(f"Retrying operation for {db_name}.{queued_write.table} (attempt {queued_write.retry_count}/{queued_write.max_retries}) after {delay}s")
                time.sleep(delay)
                
                # Re-queue the operation
                try:
                    self.queues[db_name].put(queued_write, timeout=1)
                except queue.Full:
                    logger.error(f"Failed to re-queue operation for {db_name}.{queued_write.table} - queue is full")
            else:
                logger.error(f"Max retries reached for {db_name}.{queued_write.table}, operation failed")
                # Try to reconnect database in background (non-blocking)
                if db.status != DatabaseStatus.ONLINE:
                    logger.info(f"Attempting to reconnect {db_name} database in background")
                    # Use threading to avoid blocking
                    import threading
                    reconnect_thread = threading.Thread(
                        target=db.reconnect,
                        name=f"Reconnect-{db_name}",
                        daemon=True
                    )
                    reconnect_thread.start()
    
    def _execute_operation(
        self,
        conn,
        operation: WriteOperation,
        table: str,
        data: Any
    ) -> Any:
        """Execute the actual database operation"""
        # This will be called from within execute_write, which has mutex protection
        # The actual SQL execution depends on the operation type and table
        # This is a placeholder - repositories will provide the actual SQL
        
        # For now, we'll use a generic approach
        # Repositories should provide operation handlers
        if isinstance(data, dict) and "sql" in data and "params" in data:
            # Direct SQL execution
            cursor = conn.execute(data["sql"], data["params"])
            if operation == WriteOperation.CREATE:
                return cursor.lastrowid
            return cursor.rowcount
        else:
            # This should be handled by repository-specific code
            raise NotImplementedError(f"Operation {operation.value} for table {table} not implemented")
    
    def _get_database(self, db_name: str) -> Optional[BaseDatabase]:
        """Get database instance by name"""
        if db_name == "models":
            return self.db_manager.models_db
        elif db_name == "users":
            return self.db_manager.users_db
        elif db_name == "logs":
            return self.db_manager.logs_db
        return None
    
    def get_queue_size(self, db_name: str) -> int:
        """Get current queue size for a database"""
        if db_name in self.queues:
            return self.queues[db_name].qsize()
        return 0
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """Get queue sizes for all databases"""
        return {name: queue.qsize() for name, queue in self.queues.items()}


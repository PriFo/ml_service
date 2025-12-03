"""Scheduler for orchestrating job execution"""
import asyncio
import logging
import psutil
from typing import Optional, Dict, Any

from ml_service.core.priority_queue import PriorityQueue
from ml_service.core.worker_pool import WorkerPoolManager
from ml_service.db.repositories import JobRepository
from ml_service.db.models import Job

logger = logging.getLogger(__name__)


class Scheduler:
    """Main scheduler for job orchestration"""
    
    def __init__(self, max_workers_per_pool: int = 5):
        self.running = False
        self.priority_queue = PriorityQueue()
        self.worker_pool_manager = WorkerPoolManager(max_workers_per_pool)
        self.job_repo = JobRepository()
        self._task: Optional[asyncio.Task] = None
    
    async def run(self):
        """Main scheduler loop - runs every second"""
        self.running = True
        logger.info("Scheduler started")
        
        while self.running:
            try:
                # Step 1: Check system resources
                if not self._check_resources():
                    await asyncio.sleep(5)  # Wait 5 seconds if resources insufficient
                    continue
                
                # Step 2: Get next job from queue
                job = self.priority_queue.get_next_job()
                if not job:
                    await asyncio.sleep(1)  # No jobs, wait 1 second
                    continue
                
                # Step 3: Distribute job to worker pool
                assigned = self.worker_pool_manager.distribute_job(job)
                
                if not assigned:
                    # Job was added to pending queue (either large dataset or no idle workers)
                    # For large datasets, we could trigger chunking here
                    dataset_size = job.dataset_size or 0
                    if dataset_size > 100000:
                        logger.info(f"Job {job.job_id} has large dataset, will be chunked")
                        # TODO: Trigger chunking process
                
                await asyncio.sleep(1)  # Wait 1 second before next iteration
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    def _check_resources(self) -> bool:
        """
        Check if system has enough resources.
        
        Returns: True if resources are available, False otherwise
        """
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Check thresholds
            if cpu_percent > 90:
                logger.warning(f"CPU usage too high: {cpu_percent}%")
                return False
            
            if memory_percent > 90:
                logger.warning(f"Memory usage too high: {memory_percent}%")
                return False
            
            # Check GPU if available (simplified - would need GPU detection)
            # For now, skip GPU check
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking resources: {e}", exc_info=True)
            return True  # Allow processing if check fails
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        queue_stats = self.priority_queue.get_queue_stats()
        worker_stats = self.worker_pool_manager.get_worker_stats()
        
        # Get system resources
        try:
            import multiprocessing
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = multiprocessing.cpu_count()
            memory = psutil.virtual_memory()
            
            # Try to detect GPU
            gpu_available = False
            gpu_name = None
            gpu_usage_percent = None
            try:
                from ml_service.core.gpu_detector import GPUDetector
                gpu_info = GPUDetector.detect_gpu()
                if gpu_info and gpu_info.get("available"):
                    gpu_available = True
                    gpu_name = gpu_info.get("name", "Unknown GPU")
                    gpu_usage_percent = gpu_info.get("usage_percent")
            except Exception as e:
                logger.debug(f"GPU detection failed: {e}")
                pass
            
            system_resources = {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024 ** 3),
                "memory_total_gb": memory.total / (1024 ** 3),
                "gpu_available": gpu_available,
                "gpu_name": gpu_name,
                "gpu_usage_percent": gpu_usage_percent
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            system_resources = {
                "cpu_percent": None,
                "cpu_count": None,
                "memory_percent": None,
                "memory_used_gb": None,
                "memory_total_gb": None,
                "gpu_available": False,
                "gpu_name": None,
                "gpu_usage_percent": None
            }
        
        return {
            "running": self.running,
            "queue_stats": queue_stats,
            "worker_stats": worker_stats,
            "system_resources": system_resources
        }
    
    def pause(self):
        """Pause scheduler"""
        self.running = False
        logger.info("Scheduler paused")
    
    def resume(self):
        """Resume scheduler"""
        if not self.running:
            self.running = True
            logger.info("Scheduler resumed")
            # Restart the loop if task is not running
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self.run())
    
    async def start(self):
        """Start scheduler"""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self.run())
            logger.info("Scheduler started")
    
    async def stop(self):
        """Stop scheduler"""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")


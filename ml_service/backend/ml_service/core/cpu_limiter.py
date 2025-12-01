"""CPU resource management"""
import multiprocessing
import psutil
from typing import Optional
from ml_service.core.config import settings


class CPULimiter:
    """Manage CPU resources for training jobs"""
    
    @staticmethod
    def get_available_cpus() -> int:
        """Get number of available CPU cores"""
        return multiprocessing.cpu_count()
    
    @staticmethod
    def get_cpu_usage() -> float:
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=0.1)
    
    @staticmethod
    def can_start_job() -> bool:
        """Check if we can start a new training job"""
        available = CPULimiter.get_available_cpus()
        usage = CPULimiter.get_cpu_usage()
        
        # Don't start if CPU usage is too high
        if usage > 90:
            return False
        
        # Check if we have enough workers
        active_workers = CPULimiter.count_active_workers()
        max_workers = min(
            settings.ML_MAX_WORKERS_LIMIT,
            int(available * settings.ML_WORKER_CPU_PER_TASK)
        )
        
        return active_workers < max_workers
    
    @staticmethod
    def count_active_workers() -> int:
        """Count active training workers"""
        # In production, this would query the database
        # For now, return a simple count
        return 0


"""CPU resource management with affinity control"""
import os
import multiprocessing
import threading
import logging
import psutil
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ml_service.core.config import settings

logger = logging.getLogger(__name__)


class CPUManager:
    """Manage CPU resources and affinity for different task types"""
    
    @classmethod
    def _get_allocation_percentages(cls) -> Dict[str, float]:
        """Get CPU allocation percentages from settings"""
        return {
            "ui": settings.ML_CPU_UI_RESPONSE_PERCENT,
            "api": settings.ML_CPU_API_RESPONSE_PERCENT,
            "train_predict": settings.ML_CPU_TRAIN_PREDICT_PERCENT,
            "reserve": settings.ML_CPU_RESERVE_PERCENT
        }
    
    _total_cores: Optional[int] = None
    _core_allocation: Optional[Dict[str, List[int]]] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_total_cores(cls) -> int:
        """Get total number of CPU cores"""
        if cls._total_cores is None:
            cls._total_cores = multiprocessing.cpu_count()
            logger.info(f"Detected {cls._total_cores} CPU cores")
        return cls._total_cores
    
    @classmethod
    def _calculate_core_allocation(cls) -> Dict[str, List[int]]:
        """Calculate which cores are allocated to which task type"""
        total_cores = cls.get_total_cores()
        percentages = cls._get_allocation_percentages()
        
        # Calculate number of cores for each task type
        ui_cores = max(1, int(total_cores * percentages["ui"]))
        api_cores = max(1, int(total_cores * percentages["api"]))
        train_predict_cores = max(1, int(total_cores * percentages["train_predict"]))
        reserve_cores = total_cores - ui_cores - api_cores - train_predict_cores
        
        # Allocate cores sequentially
        cores = list(range(total_cores))
        allocation = {
            "ui": cores[:ui_cores],
            "api": cores[ui_cores:ui_cores + api_cores],
            "train_predict": cores[ui_cores + api_cores:ui_cores + api_cores + train_predict_cores],
            "reserve": cores[ui_cores + api_cores + train_predict_cores:]
        }
        
        logger.info(
            f"CPU allocation: UI={len(allocation['ui'])}, API={len(allocation['api'])}, "
            f"Train/Predict={len(allocation['train_predict'])}, Reserve={len(allocation['reserve'])}"
        )
        
        return allocation
    
    @classmethod
    def get_cores_for_task(cls, task_type: str) -> List[int]:
        """
        Get CPU cores allocated for a specific task type.
        
        Args:
            task_type: One of 'ui', 'api', 'train_predict', 'reserve'
        
        Returns:
            List of CPU core indices
        """
        with cls._lock:
            if cls._core_allocation is None:
                cls._core_allocation = cls._calculate_core_allocation()
            
            cores = cls._core_allocation.get(task_type, cls._core_allocation["reserve"])
            return cores.copy()
    
    @classmethod
    def get_max_workers_for_predict(cls) -> int:
        """Get maximum number of workers for prediction tasks (80% of cores)"""
        cores = cls.get_cores_for_task("train_predict")
        return len(cores)
    
    @classmethod
    def get_max_workers_for_training(cls) -> int:
        """Get maximum number of workers for training tasks (80% of cores)"""
        cores = cls.get_cores_for_task("train_predict")
        return len(cores)
    
    @classmethod
    @contextmanager
    def set_cpu_affinity(cls, task_type: str):
        """
        Context manager to set CPU affinity for current thread/process.
        
        Args:
            task_type: One of 'ui', 'api', 'train_predict', 'reserve'
        
        Usage:
            with CPUManager.set_cpu_affinity('train_predict'):
                # Code that should run on train_predict cores
                pass
        """
        cores = cls.get_cores_for_task(task_type)
        
        if not cores:
            logger.warning(f"No cores allocated for task type '{task_type}', using all cores")
            yield
            return
        
        # Get current process
        process = None
        original_affinity = None
        
        try:
            process = psutil.Process(os.getpid())
            original_affinity = process.cpu_affinity()
            
            # Set new affinity
            try:
                process.cpu_affinity(cores)
                logger.debug(f"Set CPU affinity to cores {cores} for task type '{task_type}'")
            except (OSError, ValueError) as e:
                # On some systems (e.g., Windows without admin rights), setting affinity may fail
                logger.warning(f"Failed to set CPU affinity: {e}. Continuing without affinity restriction.")
                yield
                return
        except Exception as e:
            logger.error(f"Error setting up CPU affinity: {e}", exc_info=True)
            yield
            return
        
        # Execute the code block
        try:
            yield
        finally:
            # Restore original affinity if it was set
            if process is not None and original_affinity is not None:
                try:
                    process.cpu_affinity(original_affinity)
                    logger.debug(f"Restored CPU affinity to cores {original_affinity}")
                except (OSError, ValueError) as e:
                    logger.warning(f"Failed to restore CPU affinity: {e}")
    
    @classmethod
    def get_cpu_usage(cls) -> float:
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=0.1)
    
    @classmethod
    def get_cpu_stats(cls) -> Dict[str, Any]:
        """Get comprehensive CPU statistics"""
        total_cores = cls.get_total_cores()
        usage = cls.get_cpu_usage()
        
        with cls._lock:
            if cls._core_allocation is None:
                cls._core_allocation = cls._calculate_core_allocation()
        
        return {
            "total_cores": total_cores,
            "current_usage_percent": usage,
            "allocation": {
                "ui_cores": len(cls._core_allocation["ui"]),
                "api_cores": len(cls._core_allocation["api"]),
                "train_predict_cores": len(cls._core_allocation["train_predict"]),
                "reserve_cores": len(cls._core_allocation["reserve"])
            },
            "core_indices": {
                "ui": cls._core_allocation["ui"],
                "api": cls._core_allocation["api"],
                "train_predict": cls._core_allocation["train_predict"],
                "reserve": cls._core_allocation["reserve"]
            }
        }
    
    @classmethod
    def reset_allocation(cls):
        """Reset core allocation (useful for testing or reconfiguration)"""
        with cls._lock:
            cls._core_allocation = None
            logger.info("CPU allocation reset")


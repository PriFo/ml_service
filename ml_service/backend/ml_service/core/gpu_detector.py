"""GPU detection and backend selection"""
import logging
from typing import Literal

logger = logging.getLogger(__name__)


class GPUDetector:
    """Detect available GPUs and select ML backend"""
    
    _available_gpus: int = 0
    _checked: bool = False
    
    @classmethod
    def detect_available_gpus(cls) -> int:
        """Return number of available GPUs (0 if none)"""
        if cls._checked:
            return cls._available_gpus
        
        try:
            import subprocess
            import sys
            
            # On Windows, handle subprocess differently
            is_windows = sys.platform == "win32"
            
            # Prepare subprocess arguments
            subprocess_args = {
                "args": ["nvidia-smi", "--list-gpus"],
                "capture_output": True,
                "text": True,
                "timeout": 5
            }
            
            # On Windows, add CREATE_NO_WINDOW flag if available
            if is_windows and hasattr(subprocess, 'CREATE_NO_WINDOW'):
                subprocess_args["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(**subprocess_args)
            if result.returncode == 0 and result.stdout:
                gpu_lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
                cls._available_gpus = len(gpu_lines)
                if cls._available_gpus > 0:
                    logger.info(f"Detected {cls._available_gpus} GPU(s)")
            else:
                cls._available_gpus = 0
        except FileNotFoundError:
            # nvidia-smi not found, no GPU available
            logger.debug("nvidia-smi not found, no GPU available")
            cls._available_gpus = 0
        except subprocess.TimeoutExpired:
            logger.debug("GPU detection timed out")
            cls._available_gpus = 0
        except subprocess.SubprocessError as e:
            logger.debug(f"Subprocess error during GPU detection: {e}")
            cls._available_gpus = 0
        except Exception as e:
            # Catch any other exceptions (OSError, ValueError, etc.)
            logger.debug(f"GPU detection failed: {type(e).__name__}: {e}")
            cls._available_gpus = 0
        
        cls._checked = True
        return cls._available_gpus
    
    @classmethod
    def should_use_cuml(cls, dataset_size: int) -> bool:
        """
        Decide: use cuML or scikit-learn?
        - If GPU available and dataset > 100k rows: YES
        - If GPU available but dataset < 100k: NO (overhead)
        - Otherwise: NO
        """
        gpu_count = cls.detect_available_gpus()
        
        if gpu_count == 0:
            return False
        
        # Only use cuML for large datasets (overhead not worth it for small ones)
        if dataset_size >= 100000:
            try:
                import cuml
                logger.info(f"Using cuML backend for dataset size {dataset_size}")
                return True
            except ImportError:
                logger.warning("cuML not available, falling back to scikit-learn")
                return False
        
        return False
    
    @classmethod
    def get_backend(cls, dataset_size: int) -> Literal["cuml", "sklearn"]:
        """Return 'cuml' or 'sklearn'"""
        if cls.should_use_cuml(dataset_size):
            return "cuml"
        return "sklearn"


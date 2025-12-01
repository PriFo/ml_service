"""Core component tests"""
import pytest

from ml_service.core.gpu_detector import GPUDetector
from ml_service.core.config import settings


def test_gpu_detector():
    """Test GPU detector"""
    gpus = GPUDetector.detect_available_gpus()
    assert isinstance(gpus, int)
    assert gpus >= 0


def test_gpu_backend_selection():
    """Test backend selection logic"""
    # Small dataset should not use cuML even with GPU
    backend = GPUDetector.get_backend(50000)
    assert backend == "sklearn"
    
    # Large dataset might use cuML if GPU available
    backend = GPUDetector.get_backend(200000)
    # Result depends on GPU availability, but should be valid
    assert backend in ["sklearn", "cuml"]


def test_config_hidden_layers():
    """Test hidden layer size calculation"""
    small = settings.get_hidden_layer_sizes(5000)
    assert len(small) == 2  # (128, 64)
    
    medium = settings.get_hidden_layer_sizes(50000)
    assert len(medium) == 2  # (256, 128)
    
    large = settings.get_hidden_layer_sizes(200000)
    assert len(large) == 3  # (512, 256, 128)
    
    xlarge = settings.get_hidden_layer_sizes(600000)
    assert len(xlarge) == 4  # (1024, 512, 256, 128)


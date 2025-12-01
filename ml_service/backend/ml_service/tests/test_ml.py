"""ML component tests"""
import pytest
import numpy as np

from ml_service.ml.validators import DataValidator
from ml_service.ml.drift_detector import DriftDetector


def test_data_validator_training_data():
    """Test data validator for training data"""
    validator = DataValidator(
        feature_fields=["name", "description"],
        target_field="label"
    )
    
    valid_items = [
        {"name": "Test", "description": "Test desc", "label": "A"}
    ]
    
    invalid_items = [
        {"name": "Test"}  # Missing fields
    ]
    
    valid, invalid = validator.validate_training_data(valid_items + invalid_items)
    
    assert len(valid) == 1
    assert len(invalid) == 1
    assert invalid[0]["errors"][0].startswith("Missing")


def test_data_validator_prediction_data():
    """Test data validator for prediction data"""
    validator = DataValidator(
        feature_fields=["name", "description"],
        target_field=None
    )
    
    valid_items = [
        {"name": "Test", "description": "Test desc"}
    ]
    
    invalid_items = [
        {"name": "Test"}  # Missing description
    ]
    
    valid, invalid = validator.validate_prediction_data(valid_items + invalid_items)
    
    assert len(valid) == 1
    assert len(invalid) == 1


def test_drift_detector_psi():
    """Test PSI calculation"""
    detector = DriftDetector()
    
    # Create two similar distributions
    expected = np.random.normal(0, 1, 1000)
    actual = np.random.normal(0.1, 1, 1000)
    
    psi = detector.calculate_psi(expected, actual)
    
    assert psi >= 0
    assert isinstance(psi, float)


def test_drift_detector_js_divergence():
    """Test JS divergence calculation"""
    detector = DriftDetector()
    
    # Create two distributions
    p = np.array([0.3, 0.3, 0.4])
    q = np.array([0.4, 0.4, 0.2])
    
    js = detector.calculate_js_divergence(p, q)
    
    assert js >= 0
    assert isinstance(js, float)


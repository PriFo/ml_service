"""API endpoint tests"""
import pytest
from fastapi.testclient import TestClient

from ml_service.api.app import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_models_endpoint_unauthorized():
    """Test models endpoint without auth"""
    response = client.get("/models")
    # Should return 401 or 403 without token
    assert response.status_code in [401, 403]


def test_predict_endpoint_unauthorized():
    """Test predict endpoint without auth"""
    response = client.post("/predict", json={
        "model_key": "test",
        "data": []
    })
    assert response.status_code in [401, 403]


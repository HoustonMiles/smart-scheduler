"""
Basic tests for Smart Scheduler backend
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_read_main():
    """Test that the app starts without errors"""
    assert app is not None


def test_auth_endpoint_exists():
    """Test that auth endpoints are registered"""
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert "authenticated" in data or "message" in data


def test_tasks_endpoint_requires_auth():
    """Test that tasks endpoint requires authentication"""
    response = client.get("/tasks/")
    assert response.status_code in [401, 403]

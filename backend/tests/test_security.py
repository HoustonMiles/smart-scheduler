"""
Security tests for authentication and authorization
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.core.auth.jwt import create_access_token, decode_access_token
from fastapi import HTTPException


def test_jwt_token_creation():
    """Test that JWT tokens are created correctly"""
    user_data = {"sub": 123, "email": "test@example.com"}
    token = create_access_token(user_data)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_jwt_token_decoding():
    """Test that JWT tokens can be decoded"""
    user_data = {"sub": 123, "email": "test@example.com"}
    token = create_access_token(user_data)
    
    decoded = decode_access_token(token)
    
    assert decoded["sub"] == "123"  # Note: converted to string
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded


def test_invalid_token_rejected():
    """Test that invalid tokens are rejected"""
    invalid_token = "invalid.token.here"
    
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(invalid_token)
    
    assert exc_info.value.status_code == 401


def test_expired_token_rejected():
    """Test that expired tokens are rejected"""
    user_data = {"sub": 123, "email": "test@example.com"}
    
    # Create token that expires immediately
    token = create_access_token(
        user_data, 
        expires_delta=timedelta(seconds=-1)
    )
    
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    
    assert exc_info.value.status_code == 401


def test_unauthenticated_task_access(client):
    """Test that unauthenticated users cannot access tasks"""
    response = client.get("/tasks/")
    assert response.status_code in [401, 403]
    
    response = client.post("/tasks/", json={
        "title": "Test",
        "total_duration": 60,
        "min_session": 30,
        "max_session": 60,
        "due_date": "2025-12-31",
        "priority": 1
    })
    assert response.status_code in [401, 403]


def test_unauthenticated_scheduler_access(client):
    """Test that unauthenticated users cannot access scheduler"""
    response = client.post("/scheduler/")
    assert response.status_code in [401, 403]


def test_unauthenticated_settings_access(client):
    """Test that unauthenticated users cannot access settings"""
    response = client.get("/settings/")
    assert response.status_code in [401, 403]
    
    response = client.post("/settings/", json={
        "min_hour": 9,
        "max_hour": 18,
        "buffer_minutes": 60
    })
    assert response.status_code in [401, 403]

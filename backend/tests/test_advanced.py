"""
Advanced integration tests for Smart Scheduler
"""
import pytest
from datetime import date, timedelta
from app.models.database_models import TaskDB
from app.scheduler.balanced_strategy import BalancedStrategy


def test_task_requires_authentication(client):
    """
    Test that task endpoints reject unauthenticated requests
    """
    # Try to get tasks without auth
    response = client.get("/tasks/")
    assert response.status_code in [401, 403]
    
    # Try to create task without auth
    task_data = {
        "title": "Test",
        "total_duration": 60,
        "min_session": 30,
        "max_session": 60,
        "due_date": date.today().isoformat(),
        "priority": 1
    }
    response = client.post("/tasks/", json=task_data)
    assert response.status_code in [401, 403]


def test_settings_requires_authentication(client):
    """
    Test that settings endpoints require authentication
    """
    response = client.get("/settings/")
    assert response.status_code in [401, 403]


def test_split_sessions_exact_multiple():
    """
    Test session splitting with exact multiples
    """
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=180,
        min_len=60,
        max_len=60
    )
    
    assert len(sessions) == 3
    assert all(s == 60 for s in sessions)
    assert sum(sessions) == 180


def test_split_sessions_with_remainder():
    """
    Test session splitting with remainder
    """
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=100,
        min_len=30,
        max_len=60
    )
    
    assert sum(sessions) == 100
    assert all(s >= 30 for s in sessions)
    assert len(sessions) >= 2


def test_split_sessions_small_duration():
    """
    Test session splitting with small duration
    """
    strategy = BalancedStrategy()
    
    sessions = strategy._split_sessions(
        total_minutes=45,
        min_len=30,
        max_len=60
    )
    
    assert sum(sessions) == 45
    assert len(sessions) >= 1

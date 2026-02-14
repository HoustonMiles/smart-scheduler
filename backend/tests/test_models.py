"""
Test database models
"""
import pytest
from datetime import date
from app.models.database_models import TaskDB


def test_task_model_creation():
    """Test that TaskDB model can be instantiated"""
    task = TaskDB(
        user_id=1,
        title="Test Task",
        total_duration=60,
        min_session=30,
        max_session=60,
        due_date=date.today(),
        priority=1
    )
    
    assert task.title == "Test Task"
    assert task.total_duration == 60
    assert task.priority == 1

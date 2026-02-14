"""
Integration tests that actually use the database
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import select

from app.models.database_models import TaskDB, UserSettingsDB, User

@pytest.mark.asyncio
async def test_create_task_in_database(db_session, test_user):
    """Test creating a task and verifying it's saved to database"""
    # Add user first
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)
    
    # Create task
    task = TaskDB(
        user_id=test_user.id,
        title="Integration Test Task",
        total_duration=90,
        min_session=30,
        max_session=60,
        due_date=date.today() + timedelta(days=5),
        priority=1,
        allow_overlap=0,
        once_per_day=0
    )
    
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    
    # Verify task was saved
    result = await db_session.execute(
        select(TaskDB).where(TaskDB.user_id == test_user.id)
    )
    tasks = result.scalars().all()
    
    assert len(tasks) == 1
    assert tasks[0].title == "Integration Test Task"
    assert tasks[0].user_id == test_user.id
    assert tasks[0].total_duration == 90


@pytest.mark.asyncio
async def test_user_task_isolation(db_session, test_user, test_user_2):
    """Test that users can only see their own tasks"""
    # Add both users
    db_session.add(test_user)
    db_session.add(test_user_2)
    await db_session.commit()
    
    # Create task for user 1
    task1 = TaskDB(
        user_id=test_user.id,
        title="User 1 Task",
        total_duration=60,
        min_session=30,
        max_session=60,
        due_date=date.today(),
        priority=1
    )
    
    # Create task for user 2
    task2 = TaskDB(
        user_id=test_user_2.id,
        title="User 2 Task",
        total_duration=60,
        min_session=30,
        max_session=60,
        due_date=date.today(),
        priority=1
    )
    
    db_session.add(task1)
    db_session.add(task2)
    await db_session.commit()
    
    # Verify user 1 only sees their task
    result = await db_session.execute(
        select(TaskDB).where(TaskDB.user_id == test_user.id)
    )
    user1_tasks = result.scalars().all()
    
    assert len(user1_tasks) == 1
    assert user1_tasks[0].title == "User 1 Task"
    
    # Verify user 2 only sees their task
    result = await db_session.execute(
        select(TaskDB).where(TaskDB.user_id == test_user_2.id)
    )
    user2_tasks = result.scalars().all()
    
    assert len(user2_tasks) == 1
    assert user2_tasks[0].title == "User 2 Task"


@pytest.mark.asyncio
async def test_user_settings_creation(db_session, test_user):
    """Test creating user settings"""
    db_session.add(test_user)
    await db_session.commit()
    
    settings = UserSettingsDB(
        user_id=test_user.id,
        min_hour=9,
        max_hour=18,
        buffer_minutes=60
    )
    
    db_session.add(settings)
    await db_session.commit()
    
    # Verify settings saved
    result = await db_session.execute(
        select(UserSettingsDB).where(UserSettingsDB.user_id == test_user.id)
    )
    saved_settings = result.scalar_one_or_none()
    
    assert saved_settings is not None
    assert saved_settings.min_hour == 9
    assert saved_settings.max_hour == 18


@pytest.mark.asyncio
async def test_task_cascade_delete(db_session, test_user):
    """Test that deleting a user cascades to their tasks"""
    db_session.add(test_user)
    await db_session.commit()
    
    # Create task for user
    task = TaskDB(
        user_id=test_user.id,
        title="Task to be deleted",
        total_duration=60,
        min_session=30,
        max_session=60,
        due_date=date.today(),
        priority=1
    )
    db_session.add(task)
    await db_session.commit()
    
    # Delete user
    await db_session.delete(test_user)
    await db_session.commit()
    
    # Verify task was also deleted
    result = await db_session.execute(
        select(TaskDB).where(TaskDB.user_id == test_user.id)
    )
    tasks = result.scalars().all()
    
    assert len(tasks) == 0

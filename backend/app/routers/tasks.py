"""
Task management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete as sql_delete
from datetime import date
from pydantic import BaseModel

from app.database import get_session
from app.models.database_models import User, TaskDB, CalendarEventDB
from app.core.auth.jwt import get_current_user
from app.core.auth.deps import get_gc_for_user
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.schemas.responses import StandardResponse
from app.core.logging_config import logger

router = APIRouter()


# Inline model definition
class TaskCreate(BaseModel):
    title: str
    total_duration: int
    min_session: int
    max_session: int
    due_date: date
    priority: int
    allow_overlap: bool = False
    once_per_day: bool = False


@router.post("/", response_model=StandardResponse)
async def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new task for the current user"""
    # Validate dates
    if task.due_date < date.today():
        raise create_http_exception(
            ValidationError("Due date cannot be in the past")
        )

    # Create task
    new_task = TaskDB(
        user_id=current_user.id,
        title=task.title,
        total_duration=task.total_duration,
        min_session=task.min_session,
        max_session=task.max_session,
        due_date=task.due_date,
        priority=task.priority,
        allow_overlap=1 if task.allow_overlap else 0,
        once_per_day=1 if task.once_per_day else 0,
    )

    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)

    return StandardResponse(
        message="Task created successfully",
        data={"id": new_task.id, "title": new_task.title}
    )


@router.get("/")
async def get_tasks(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get all tasks for the current user"""
    result = await session.execute(
        select(TaskDB).where(TaskDB.user_id == current_user.id)
    )
    tasks = result.scalars().all()

    return [
        {
            "id": task.id,
            "title": task.title,
            "total_duration": task.total_duration,
            "min_session": task.min_session,
            "max_session": task.max_session,
            "due_date": task.due_date.isoformat(),
            "priority": task.priority,
            "status": task.status,
            "allow_overlap": bool(task.allow_overlap),
            "once_per_day": bool(task.once_per_day),
        }
        for task in tasks
    ]


@router.get("/{task_id}")
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific task"""
    result = await session.execute(
        select(TaskDB).where(
            TaskDB.id == task_id,
            TaskDB.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise create_http_exception(ResourceNotFoundError("Task not found"))

    return {
        "id": task.id,
        "title": task.title,
        "total_duration": task.total_duration,
        "min_session": task.min_session,
        "max_session": task.max_session,
        "due_date": task.due_date.isoformat(),
        "priority": task.priority,
        "status": task.status,
        "allow_overlap": bool(task.allow_overlap),
        "once_per_day": bool(task.once_per_day),
    }


@router.get("/{task_id}/sessions")
async def get_task_sessions(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all scheduled calendar sessions for a specific task"""
    # Verify task belongs to user
    result = await session.execute(
        select(TaskDB).where(
            TaskDB.id == task_id,
            TaskDB.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise create_http_exception(ResourceNotFoundError("Task not found"))
    
    # Get all calendar events for this task
    result = await session.execute(
        select(CalendarEventDB)
        .where(CalendarEventDB.task_id == task_id)
        .order_by(CalendarEventDB.start)
    )
    events = result.scalars().all()
    
    return StandardResponse(
        message=f"Found {len(events)} sessions",
        data={
            "task": {
                "id": task.id,
                "title": task.title,
                "total_duration": task.total_duration,
                "priority": task.priority
            },
            "sessions": [
                {
                    "id": ev.id,
                    "google_event_id": ev.google_event_id,
                    "start": ev.start.strftime('%Y-%m-%dT%H:%M:%S') if ev.start else None,
                    "end": ev.end.strftime('%Y-%m-%dT%H:%M:%S') if ev.end else None,
                    "duration_minutes": int((ev.end - ev.start).total_seconds() / 60) if ev.start and ev.end else 0,
                    # CRITICAL: Frontend needs these fields
                    "taskTitle": task.title,
                    "taskId": task.id,
                    "priority": task.priority
                }
                for ev in events
            ]
        }
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a task and all its calendar events.
    
    FIXED: Now properly deletes from both database AND Google Calendar.
    """
    # Verify task belongs to user
    result = await session.execute(
        select(TaskDB).where(
            TaskDB.id == task_id,
            TaskDB.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise create_http_exception(ResourceNotFoundError("Task not found"))

    # Get Google Calendar service for this user
    gc = await get_gc_for_user(current_user.id, session)
    
    # Get all calendar events for this task BEFORE deleting from DB
    result = await session.execute(
        select(CalendarEventDB).where(CalendarEventDB.task_id == task_id)
    )
    calendar_events = result.scalars().all()
    
    deleted_from_google = 0
    failed_to_delete = 0
    
    # Delete from Google Calendar first
    if gc:
        for event in calendar_events:
            try:
                logger.info(f"Deleting Google Calendar event: {event.google_event_id}")
                gc.delete_event(event.google_event_id)
                deleted_from_google += 1
            except Exception as e:
                logger.warning(f"Failed to delete event {event.google_event_id} from Google Calendar: {e}")
                failed_to_delete += 1
    else:
        logger.warning(f"No Google Calendar service available for user {current_user.id}")
    
    # Delete all calendar events from database
    await session.execute(
        sql_delete(CalendarEventDB).where(CalendarEventDB.task_id == task_id)
    )

    # Delete the task
    await session.delete(task)
    await session.commit()
    
    logger.info(f"Task {task_id} deleted: {deleted_from_google} events removed from Google Calendar, {failed_to_delete} failed")

    return StandardResponse(
        message=f"Task deleted successfully. Removed {deleted_from_google} events from calendar.",
        data={
            "id": task_id,
            "deleted_from_google": deleted_from_google,
            "failed": failed_to_delete
        }
    )


@router.put("/{task_id}")
async def update_task(
    task_id: int,
    task_update: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a task"""
    # Verify task belongs to user
    result = await session.execute(
        select(TaskDB).where(
            TaskDB.id == task_id,
            TaskDB.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise create_http_exception(ResourceNotFoundError("Task not found"))

    # Update fields
    task.title = task_update.title
    task.total_duration = task_update.total_duration
    task.min_session = task_update.min_session
    task.max_session = task_update.max_session
    task.due_date = task_update.due_date
    task.priority = task_update.priority
    task.allow_overlap = 1 if task_update.allow_overlap else 0
    task.once_per_day = 1 if task_update.once_per_day else 0

    await session.commit()

    return StandardResponse(
        message="Task updated successfully",
        data={"id": task.id, "title": task.title}
    )


def create_http_exception(exc):
    """Helper to create HTTP exceptions"""
    from fastapi import HTTPException
    return HTTPException(status_code=exc.status_code if hasattr(exc, 'status_code') else 400, detail=str(exc))

"""
Scheduler endpoint - triggers the scheduling algorithm
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models.database_models import User, TaskDB, CalendarEventDB, UserSettingsDB
from app.core.auth.jwt import get_current_user
from app.core.auth.deps import get_gc_for_user
from app.core.exceptions import ValidationError, create_http_exception
from app.schemas.responses import StandardResponse
from app.scheduler.task_scheduler import TaskScheduler

router = APIRouter()


@router.post("/", response_model=StandardResponse)
async def schedule_tasks(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Run the scheduling algorithm for all pending tasks.
    Creates calendar events in Google Calendar.
    """
    # Get user's pending tasks
    result = await session.execute(
        select(TaskDB).where(
            TaskDB.user_id == current_user.id,
            TaskDB.status == "pending"
        )
    )
    tasks = result.scalars().all()

    if not tasks:
        raise create_http_exception(
            ValidationError("No pending tasks to schedule")
        )

    # Get Google Calendar for user
    gc = await get_gc_for_user(current_user.id, session)
    if not gc:
        raise create_http_exception(
            ValidationError("Google Calendar not configured. Please login first.")
        )

    # Get user settings
    result = await session.execute(
        select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    min_hour = settings.min_hour if settings else 9
    max_hour = settings.max_hour if settings else 18
    buffer_minutes = settings.buffer_minutes if settings else 60

    # Create scheduler with GoogleCalendar object (NOT user!)
    scheduler = TaskScheduler(gc, min_hour, max_hour, buffer_minutes)
    
    # Run the scheduler
    await scheduler.schedule_all(tasks, session)

    # Get all sessions that were just created
    all_sessions = []
    for task in tasks:
        result = await session.execute(
            select(CalendarEventDB)
            .where(CalendarEventDB.task_id == task.id)
            .order_by(CalendarEventDB.start)
        )
        events = result.scalars().all()
        
        all_sessions.append({
            "task_id": task.id,
            "task_title": task.title,
            "sessions": [
                {
                    "start": ev.start.isoformat() if ev.start else None,
                    "end": ev.end.isoformat() if ev.end else None,
                    "duration_minutes": int((ev.end - ev.start).total_seconds() / 60) if ev.start and ev.end else 0
                }
                for ev in events
            ]
        })

    return StandardResponse(
        message=f"Successfully scheduled {len(tasks)} tasks",
        data={"scheduled": all_sessions}
    )

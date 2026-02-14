from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from app.database import get_session
from app.models.database_models import TaskDB, CalendarEventDB, User
from app.scheduler.task_scheduler import _parse_taskid
from app.core.auth.jwt import get_current_user
from app.core.auth.deps import get_gc_for_user
from app.core.logging_config import logger
from app.schemas.responses import StandardResponse
from app.core.exceptions import (
    AuthenticationError,
    CalendarNotConfiguredError,
    ResourceNotFoundError,
    create_http_exception
)

router = APIRouter(tags=["sync"])

@router.post("")
@router.post("/")
async def sync_calendar(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    gc = await get_gc_for_user(current_user.id, session)
    if not gc:
        return StandardResponse(message="⚠️ Google Calendar not initialized. Please login first.")
    
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    end = now + timedelta(days=365)
    events = gc.list_events(start, end)
    event_map = {e["id"]: e for e in events}
    
    for ev in events:
        tid = _parse_taskid(ev.get("description", ""))
        if not tid:
            continue
        
        # Only sync THIS user's tasks
        result = await session.execute(
            select(TaskDB).where(
                TaskDB.id == tid,
                TaskDB.user_id == current_user.id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            continue
        
        result = await session.execute(
            select(CalendarEventDB).where(CalendarEventDB.google_event_id == ev["id"])
        )
        ce = result.scalar_one_or_none()
        start_dt = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
        if ce:
            ce.start = start_dt
            ce.end = end_dt
        else:
            ce = CalendarEventDB(
                google_event_id=ev["id"], task_id=task.id, start=start_dt, end=end_dt
            )
            session.add(ce)
    
    # Only check THIS user's events
    result = await session.execute(
        select(CalendarEventDB)
        .join(TaskDB)
        .where(TaskDB.user_id == current_user.id)
    )
    db_events = result.scalars().all()
    for db_ev in db_events:
        if db_ev.google_event_id not in event_map:
            await session.delete(db_ev)
    
    await session.commit()
    return StandardResponse(message="sync complete")

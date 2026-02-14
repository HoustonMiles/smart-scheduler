from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_session
from app.models.database_models import UserSettingsDB, User
from app.core.auth.jwt import get_current_user
from pydantic import BaseModel
from app.schemas.responses import StandardResponse
from app.core.exceptions import (
    AuthenticationError,
    CalendarNotConfiguredError,
    ResourceNotFoundError,
    create_http_exception
)

router = APIRouter(tags=["settings"])

class SettingsIn(BaseModel):
    min_hour: int
    max_hour: int
    buffer_minutes: int

@router.post("/")
async def update_settings(
    settings: SettingsIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    # Get THIS user's settings
    result = await session.execute(
        select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.min_hour = settings.min_hour
        existing.max_hour = settings.max_hour
        existing.buffer_minutes = settings.buffer_minutes
    else:
        existing = UserSettingsDB(
            user_id=current_user.id,
            min_hour=settings.min_hour,
            max_hour=settings.max_hour,
            buffer_minutes=settings.buffer_minutes,
        )
        session.add(existing)
    
    await session.commit()
    return StandardResponse(message="Settings saved", data={"settings": settings.dict()})

@router.get("/")
async def get_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(UserSettingsDB).where(UserSettingsDB.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        return StandardResponse(message="Default settings", data={"min_hour": 9, "max_hour": 18, "buffer_minutes": 60})
    
    return StandardResponse(
        message="Settings retrieved",
        data={
            "min_hour": settings.min_hour,
            "max_hour": settings.max_hour,
            "buffer_minutes": settings.buffer_minutes
        }
    )

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from app.models.database_models import UserSettingsDB
from app.services.google_calendar import GoogleCalendar
from app.config import SCOPES
from app.core.logging_config import logger

async def get_gc_for_user(user_id: int, session: AsyncSession) -> GoogleCalendar | None:
    """Load credentials from DB for specific user and return GoogleCalendar."""
    result = await session.execute(
        select(UserSettingsDB).where(UserSettingsDB.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.refresh_token:
        return None
    
    creds = Credentials(
        token=settings.access_token,
        refresh_token=settings.refresh_token,
        token_uri=settings.token_uri,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        scopes=settings.scopes.split(",") if settings.scopes else SCOPES,
    )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        settings.access_token = creds.token
        await session.commit()
    
    return GoogleCalendar(creds)

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
import pytz
from google.oauth2.credentials import Credentials
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging_config import logger

def priority_to_color(priority: int) -> str:
    """Map priority number to Google Calendar colorId (1–11)."""
    mapping = {
        1: "11",  # Red
        2: "4",   # Orange
        3: "5",   # Yellow
        4: "7",   # Green
        5: "9",   # Blue
    }
    return mapping.get(priority, "1")  # Default (Blue)


class GoogleCalendar:
    """
    Google Calendar API wrapper for Smart Scheduler.
    
    Handles all interactions with Google Calendar API including:
    - Fetching events
    - Creating new events
    - Deleting events
    - Managing timezone awareness
    """
    """
    Google Calendar API wrapper for Smart Scheduler.
    
    Handles all interactions with Google Calendar API including:
    - Fetching events
    - Creating new events
    - Deleting events
    - Managing timezone awareness
    """
    def __init__(self, creds: Credentials):
        self.service = build("calendar", "v3", credentials=creds)

        # Fetch primary calendar metadata to get default timezone
        calendar = self.service.calendars().get(calendarId="primary").execute()
        self.timezone = calendar["timeZone"]
        self.tz = pytz.timezone(self.timezone)

    def _ensure_aware(self, dt: datetime):
        """Force datetime to be timezone-aware in the calendar's timezone."""
        if dt.tzinfo is None:
            return self.tz.localize(dt)
        return dt.astimezone(self.tz)

    def list_events(self, start: datetime, end: datetime):
        """Fetch events between start and end datetimes."""
        start = self._ensure_aware(start)
        end = self._ensure_aware(end)

        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return events_result.get("items", [])

    def insert_event(
            self, 
            title, 
            start: datetime, 
            end: datetime, 
            description=None, 
            priority=None,
            task_id=None,
            session_index=None,
            total_sessions=None
    ):
        """Insert new event into Google Calendar."""
        start = self._ensure_aware(start)
        end = self._ensure_aware(end)

        if total_sessions and session_index is not None:
            summary = f"{title} (Part {session_index + 1}/{total_sessions})"
        else:
            summary = title

        desc_parts = []
        if description:
            desc_parts.append(description)
        if task_id:
            desc_parts.append(f"SmartScheduler TaskID: {task_id}")
        desc = "\n".join(desc_parts) if desc_parts else None

        event = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": self.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self.timezone},
        }
        if desc:
            event["description"] = desc

        if priority is not None:
            event["colorId"] = priority_to_color(priority)
        
        created = (
            self.service.events()
            .insert(calendarId="primary", body=event)
            .execute()
        )

        return created["id"]
    
    def delete_event(self, event_id: str):
        """Delete an event from Google Calendar by event ID."""
        try:
            logger.info(f"GoogleCalendar.delete_event called with event_id: {event_id}")
            
            self.service.events().delete(
                calendarId="primary",
                eventId=event_id
            ).execute()
            
            logger.info(f"Successfully deleted event {event_id} from Google Calendar")
            return True
            
        except HttpError as e:
            # Handle specific HTTP errors
            if e.resp.status == 404:
                logger.info(f"Event {event_id} not found in Google Calendar (may already be deleted)")
                return False
            elif e.resp.status == 410:
                logger.info(f"Event {event_id} was already deleted")
                return False
            else:
                logger.info(f"HTTP error deleting event {event_id}: {e}")
                raise
        except Exception as e:
            logger.info(f"Unexpected error deleting event {event_id}: {e}")
            raise

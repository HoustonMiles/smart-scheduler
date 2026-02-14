from datetime import datetime, time, timedelta
from typing import List, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.models.database_models import CalendarEventDB, TaskDB
from app.scheduler.balanced_strategy import BalancedStrategy
from app.core.logging_config import logger

TASKID_RE = re.compile(r"TaskID=(\d+)")

def _parse_taskid(desc: str) -> int | None:
    m = TASKID_RE.search(desc or "")
    return int(m.group(1)) if m else None


class TaskScheduler:
    """
    Main task scheduler coordinating task placement into calendar.
    
    FIXED ISSUES:
    - Buffer only applies to external events (not app tasks)
    - Prevents duplicate scheduling
    - Better conflict detection
    """
    
    def __init__(self, calendar, min_hour=9, max_hour=18, buffer_minutes=60):
        self.calendar = calendar
        self.strategy = BalancedStrategy()
        self.min_hour = min_hour
        self.max_hour = max_hour
        self.buffer_minutes = buffer_minutes

    async def _build_busy_times_for_task(
        self, 
        task: TaskDB, 
        day_start: datetime, 
        day_end: datetime, 
        session: AsyncSession
    ) -> List[Tuple[datetime, datetime]]:
        """
        Build list of busy time slots.
        
        CRITICAL FIX: Buffer only applies to EXTERNAL events.
        - External events (no TaskID): Block with buffer
        - App tasks (has TaskID): Block exact time without buffer
        - Same task's sessions: Don't block at all
        """
        events = self.calendar.list_events(day_start, day_end)
        busy = []

        # Pre-fetch task ownership for all events
        tids = []
        for ev in events:
            tid = _parse_taskid(ev.get("description", ""))
            if tid:
                tids.append(tid)

        tasks_map = {}
        if tids:
            result = await session.execute(select(TaskDB).where(TaskDB.id.in_(tids)))
            tasks_map = {t.id: t for t in result.scalars().all()}

        for ev in events:
            start = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00")).astimezone(self.calendar.tz)
            end = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00")).astimezone(self.calendar.tz)

            tid = _parse_taskid(ev.get("description", ""))
            
            if tid:
                # This is an APP-CREATED event
                owner = tasks_map.get(tid)
                
                # Skip if it's the same task's own session
                if owner and owner.id == task.id:
                    logger.debug(f"Skipping same task session: {start} to {end}")
                    continue
                
                # For other app tasks
                if owner and owner.allow_overlap and task.allow_overlap:
                    # Both allow overlap - don't block
                    logger.debug(f"Allowing overlap with task {owner.id}: {start} to {end}")
                    continue
                else:
                    # Block EXACT time - NO BUFFER between app tasks
                    busy.append((start, end))
                    logger.debug(f"Blocking app task {tid}: {start} to {end} (no buffer)")
            else:
                # EXTERNAL EVENT (not created by app) - ADD BUFFER
                start_with_buffer = start - timedelta(minutes=self.buffer_minutes)
                end_with_buffer = end + timedelta(minutes=self.buffer_minutes)
                busy.append((start_with_buffer, end_with_buffer))
                logger.info(f"Blocking external event: {start} to {end} (with {self.buffer_minutes}min buffer)")

        busy.sort(key=lambda x: x[0])
        return busy

    async def _get_existing_sessions(self, task_id: int, session: AsyncSession) -> List[CalendarEventDB]:
        """Get all existing calendar sessions for a task."""
        result = await session.execute(
            select(CalendarEventDB).where(CalendarEventDB.task_id == task_id)
        )
        return result.scalars().all()

    async def _place_sessions(self, sessions: List[Tuple[TaskDB, dict]], session: AsyncSession) -> None:
        """
        Insert events into Google Calendar and database.
        
        FIXED: 
        - Better conflict detection
        - Proper session numbering
        - Skips tasks that already have sessions
        """
        # Group sessions by task
        task_sessions = {}
        for task, slot in sessions:
            if task.id not in task_sessions:
                task_sessions[task.id] = []
            task_sessions[task.id].append((task, slot))
        
        # Sort each task's sessions by start time
        for task_id in task_sessions:
            task_sessions[task_id].sort(key=lambda x: x[1]["start"])
        
        placed_count = 0
        skipped_count = 0
        already_scheduled_count = 0
        
        # Place all sessions with correct numbering
        for task_id, task_slot_list in task_sessions.items():
            task_name = task_slot_list[0][0].title
            
            # CHECK: Does this task already have sessions?
            existing_sessions = await self._get_existing_sessions(task_id, session)
            if existing_sessions:
                logger.info(f"Task '{task_name}' already has {len(existing_sessions)} sessions - skipping")
                already_scheduled_count += len(task_slot_list)
                continue
            
            logger.info(f"Attempting to schedule {len(task_slot_list)} sessions for task: {task_name}")
            
            # First pass: check which sessions can be placed
            valid_sessions = []
            
            for idx, (task, s) in enumerate(task_slot_list):
                # Build busy times for conflict checking
                busy_times = await self._build_busy_times_for_task(
                    task, 
                    s["start"].replace(hour=self.min_hour, minute=0, second=0), 
                    s["end"].replace(hour=self.max_hour, minute=0, second=0), 
                    session
                )

                # Check for conflicts
                conflict = False
                for bstart, bend in busy_times:
                    # Check if this session overlaps with busy time
                    if not (s["end"] <= bstart or s["start"] >= bend):
                        conflict = True
                        logger.debug(f"Session {s['start']} to {s['end']} conflicts with {bstart} to {bend}")
                        break
                
                if conflict:
                    logger.warning(f"Cannot place session at {s['start']} for {task.title} - conflict detected")
                    skipped_count += 1
                else:
                    valid_sessions.append((task, s))
            
            # Second pass: place valid sessions with correct numbering
            total_valid_sessions = len(valid_sessions)
            
            if total_valid_sessions == 0:
                logger.warning(f"No valid time slots found for task: {task_name}")
                continue
            
            logger.info(f"Placing {total_valid_sessions} sessions for task: {task_name}")
            
            for session_index, (task, s) in enumerate(valid_sessions):
                try:
                    # Insert event into Google Calendar
                    event_id = self.calendar.insert_event(
                        task.title, 
                        s["start"], 
                        s["end"],
                        description=f"TaskID={task.id}", 
                        priority=task.priority,
                        task_id=task.id,
                        session_index=session_index,
                        total_sessions=total_valid_sessions
                    )

                    # Save to database
                    ce = CalendarEventDB(
                        google_event_id=event_id,
                        task_id=task.id,
                        start=s["start"].replace(tzinfo=None),
                        end=s["end"].replace(tzinfo=None)
                    )
                    session.add(ce)
                    
                    placed_count += 1
                    logger.info(f"[PLACED] Session {session_index + 1}/{total_valid_sessions} for {task.title}: {s['start']} - {s['end']}")
                    
                except Exception as e:
                    logger.error(f"Failed to insert event for {task.title}: {e}")
                    skipped_count += 1

        await session.commit()
        
        logger.info(f"[SUMMARY] Scheduling complete: {placed_count} placed, {skipped_count} skipped, {already_scheduled_count} already scheduled")

    async def schedule_task(self, task: TaskDB, session: AsyncSession) -> None:
        """Schedule a single task with BalancedStrategy."""
        # Check if already scheduled
        existing_sessions = await self._get_existing_sessions(task.id, session)
        if existing_sessions:
            logger.info(f"Task '{task.title}' already has {len(existing_sessions)} sessions - skipping")
            return
        
        now = datetime.now(self.calendar.tz)
        sessions = self.strategy.generate_plan(
            [task], now, self.calendar,
            self.min_hour, self.max_hour, self.buffer_minutes
        )
        logger.info(f"Generated {len(sessions)} potential sessions for {task.title}")
        await self._place_sessions(sessions, session)

    async def schedule_all(self, tasks: List[TaskDB], session: AsyncSession) -> None:
        """
        Schedule multiple tasks at once.
        
        FIXED: 
        - Checks for existing sessions
        - Better logging
        - Proper conflict resolution
        """
        if not tasks:
            logger.warning("No tasks to schedule")
            return

        # Filter out tasks that already have sessions
        tasks_to_schedule = []
        for task in tasks:
            existing_sessions = await self._get_existing_sessions(task.id, session)
            if existing_sessions:
                logger.info(f"Task '{task.title}' already scheduled with {len(existing_sessions)} sessions - skipping")
            else:
                tasks_to_schedule.append(task)
        
        if not tasks_to_schedule:
            logger.info("All tasks are already scheduled!")
            return

        now = datetime.now(self.calendar.tz)
        logger.info(f"Scheduling {len(tasks_to_schedule)} tasks (skipped {len(tasks) - len(tasks_to_schedule)} already scheduled)...")
        
        sessions = self.strategy.generate_plan(
            tasks_to_schedule, now, self.calendar,
            self.min_hour, self.max_hour, self.buffer_minutes
        )
        
        logger.info(f"Generated {len(sessions)} potential sessions across all tasks")
        await self._place_sessions(sessions, session)

    async def reschedule_task(self, task_id: int, session: AsyncSession) -> None:
        """Remove existing events for a task and re-plan it."""
        logger.info(f"Rescheduling task {task_id}")
        
        # Get existing events before deletion
        result = await session.execute(
            select(CalendarEventDB).where(CalendarEventDB.task_id == task_id)
        )
        existing_events = result.scalars().all()
        
        # Delete from Google Calendar first
        for event in existing_events:
            try:
                self.calendar.delete_event(event.google_event_id)
                logger.info(f"Deleted Google event {event.google_event_id}")
            except Exception as e:
                logger.warning(f"Error deleting event {event.google_event_id}: {e}")
        
        # Delete from DB
        await session.execute(delete(CalendarEventDB).where(CalendarEventDB.task_id == task_id))
        await session.commit()
        
        logger.info(f"Deleted {len(existing_events)} events for task {task_id}")

        # Re-fetch the task
        result = await session.execute(select(TaskDB).where(TaskDB.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found for reschedule")
            return

        await self.schedule_task(task, session)

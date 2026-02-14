from typing import List, Tuple, Any
from datetime import datetime, timedelta, time


class BalancedStrategy:
    """
    Improved balanced scheduling strategy that distributes tasks evenly.
    
    Fixes:
    - Better conflict detection respecting allow_overlap
    - More intelligent session placement
    - Better handling of once_per_day constraint
    """
    
    def __init__(self):
        pass

    def _split_sessions(self, total_minutes: int, min_len: int, max_len: int) -> List[int]:
        """Split a task into valid session chunks."""
        sessions = []
        remaining = total_minutes
        while remaining > 0:
            chunk = min(max_len, remaining)
            if chunk < min_len and sessions:
                sessions[-1] += chunk
                break
            sessions.append(chunk)
            remaining -= chunk
        return sessions

    def generate_plan(self, tasks: List[Any], now: Any, calendar: Any, min_hour: int, max_hour: int, buffer_minutes: int) -> List[Tuple[Any, dict]]:
        """
        Generate scheduling plan for all tasks.
        
        Improvements:
        - Better conflict detection
        - Respects allow_overlap properly
        - More aggressive scheduling to fill available slots
        """
        candidates = []
        
        # Generate all possible candidate slots
        for task in tasks:
            pieces = self._split_sessions(task.total_duration, task.min_session, task.max_session)
            total_days = max(1, (task.due_date - now.date()).days + 1)
            
            # For each piece of the task
            for idx, dur in enumerate(pieces):
                # Try each day up to deadline
                for offset in range(total_days):
                    day = now.date() + timedelta(days=offset)
                    day_start = calendar.tz.localize(datetime.combine(day, time(hour=min_hour)))
                    day_end = calendar.tz.localize(datetime.combine(day, time(hour=max_hour)))
                    
                    # Skip if day is in the past
                    if day_end < now:
                        continue
                    
                    # Start from now if it's today, otherwise from day_start
                    slot_start = max(day_start, now if day == now.date() else day_start)
                    
                    # Try multiple start times within the day (every 30 minutes)
                    current_time = slot_start
                    while current_time + timedelta(minutes=dur) <= day_end:
                        slot_end = current_time + timedelta(minutes=dur)
                        
                        days_until_due = (task.due_date - day).days
                        is_weekend = day.weekday() >= 5
                        
                        # Calculate priority score
                        # Higher urgency (closer to deadline) = higher score
                        # Higher priority number = higher score
                        # Prefer distributing pieces across different days
                        urgency_score = 1.0 / (days_until_due + 1)
                        priority_score = 0.5 * task.priority
                        weekend_bonus = 0.2 if is_weekend else 0
                        
                        # Encourage spacing by penalizing same-day placements
                        spacing_penalty = 0.1 * abs(offset - (idx * total_days // len(pieces)))
                        
                        score = urgency_score + priority_score + weekend_bonus - spacing_penalty
                        
                        candidates.append((task, idx, {
                            "start": current_time,
                            "end": slot_end,
                            "score": score,
                            "day": day
                        }))
                        
                        # Move to next possible start time
                        current_time += timedelta(minutes=30)
        
        # Sort candidates by score (highest first), then by start time (earliest first)
        candidates.sort(key=lambda x: (-x[2]["score"], x[2]["start"]))
        
        final = []
        placed_slots = []  # Track all placed slots with their tasks
        placed_pieces = {}  # Track which pieces of each task have been placed
        task_day_count = {}  # Track how many sessions per task per day
        
        for task, piece_idx, slot in candidates:
            # Skip if this piece is already placed
            task_id = id(task)  # Use object id as unique identifier
            if task_id not in placed_pieces:
                placed_pieces[task_id] = set()
            
            if piece_idx in placed_pieces[task_id]:
                continue
            
            # Check once_per_day constraint
            if task.once_per_day:
                day_key = (task_id, slot["day"])
                if day_key in task_day_count:
                    continue  # Already scheduled on this day
            
            # Check for conflicts with already placed slots
            has_conflict = False
            for placed_task, placed_slot in placed_slots:
                # Check if times overlap
                overlap = not (slot["end"] <= placed_slot["start"] or slot["start"] >= placed_slot["end"])
                
                if overlap:
                    # Allow overlap if BOTH tasks allow it
                    if task.allow_overlap and placed_task.allow_overlap:
                        continue  # No conflict
                    else:
                        has_conflict = True
                        break
            
            if has_conflict:
                continue
            
            # No conflicts - place this session
            final.append((task, slot))
            placed_slots.append((task, slot))
            placed_pieces[task_id].add(piece_idx)
            
            # Update day count for once_per_day tracking
            if task.once_per_day:
                day_key = (task_id, slot["day"])
                task_day_count[day_key] = True
        
        return final

from typing import List, Tuple, Any
from datetime import datetime, timedelta, time


class DeadlineFirstStrategy:
    def __init__(self):
        pass

    def _split_sessions(self, total_minutes: int, min_len: int, max_len: int) -> List[int]:
        """Split a task into multiple valid session durations."""
        sessions = []
        while total_minutes > 0:
            if total_minutes >= max_len:
                sessions.append(max_len)
                total_minutes -= max_len
            else:
                if total_minutes >= min_len:
                    sessions.append(total_minutes)
                    total_minutes = 0
                else:
                    if sessions:
                        sessions[-1] += total_minutes
                    else:
                        sessions.append(total_minutes)
                    total_minutes = 0
        return sessions

    def generate_plan(self, tasks: List[Any], now: Any, calendar: Any, min_hour: int, max_hour: int, buffer_minutes: int) -> List[Tuple[Any, dict]]:
        """
        Plan sessions for *all* tasks globally, with:
          - earliest deadline first
          - once-per-day restriction
          - buffer_minutes used as minimum gap between sessions
          - no enforced gap for overlap-allowed tasks
        """
        sessions = []
        busy = []  # occupied slots

        # sort tasks by deadline
        tasks_sorted = sorted(tasks, key=lambda t: t.due_date)

        for task in tasks_sorted:
            pieces = self._split_sessions(
                task.total_duration, task.min_session, task.max_session
            )
            current_day = now.date()
            piece_index = 0

            while piece_index < len(pieces) and current_day <= task.due_date:
                day_start = calendar.tz.localize(
                    datetime.combine(current_day, time(hour=min_hour))
                )
                day_end = calendar.tz.localize(
                    datetime.combine(current_day, time(hour=max_hour))
                )

                if day_end < now:
                    current_day += timedelta(days=1)
                    continue

                free_cursor = max(now, day_start)
                daily_sessions = 0  # track sessions placed for this task today

                while piece_index < len(pieces):
                    duration = timedelta(minutes=pieces[piece_index])

                    # respect buffer as gap unless this + last session are overlap-allowed
                    if busy and not (
                        task.allow_overlap
                        and sessions[-1][0].allow_overlap
                    ):
                        free_cursor = free_cursor + timedelta(minutes=buffer_minutes)

                    # check for conflicts
                    conflict = False
                    for b in busy:
                        if not (
                            free_cursor + duration <= b["start"]
                            or free_cursor >= b["end"]
                        ):
                            conflict = True
                            free_cursor = b["end"] + timedelta(minutes=buffer_minutes)
                            break
                    if conflict:
                        continue

                    if free_cursor + duration <= day_end:
                        slot = {"start": free_cursor, "end": free_cursor + duration}
                        sessions.append((task, slot))
                        busy.append(slot)
                        busy.sort(key=lambda x: x["start"])
                        free_cursor = slot["end"]
                        piece_index += 1
                        daily_sessions += 1

                        if getattr(task, "once_per_day", False):
                            break  # stop after one per day
                    else:
                        break  # move to next day

                current_day += timedelta(days=1)

        return sessions

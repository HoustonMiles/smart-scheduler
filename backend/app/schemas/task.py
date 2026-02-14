from dataclasses import dataclass

@dataclass
class Task:
    title: str
    total_duration: int  # in minutes
    min_session: int     # min session length (minutes)
    max_session: int     # max session length (minutes)
    due_date: str        # YYYY-MM-DD
    priority: int = 1    # optional, default = 1

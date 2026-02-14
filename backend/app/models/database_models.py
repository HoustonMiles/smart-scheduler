from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from google.oauth2.credentials import Credentials
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    google_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    settings = relationship("UserSettingsDB", back_populates="user", uselist=False)
    tasks = relationship("TaskDB", back_populates="user", cascade="all, delete-orphan")

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    total_duration = Column(Integer, nullable=False)
    min_session = Column(Integer, nullable=False)
    max_session = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    priority = Column(Integer, nullable=False)
    status = Column(String, default="pending")
    allow_overlap = Column(Integer, default=0)
    once_per_day = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="tasks")
    events = relationship("CalendarEventDB", back_populates="task", cascade="all, delete-orphan")

class CalendarEventDB(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    google_event_id = Column(String, unique=True, nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    start = Column(DateTime, nullable=True)
    end = Column(DateTime, nullable=True)

    task = relationship("TaskDB", back_populates="events")

class UserSettingsDB(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_uri = Column(String, nullable=True)
    client_id = Column(String, nullable=True)
    client_secret = Column(String, nullable=True)
    scopes = Column(String, nullable=True)

    min_hour = Column(Integer, default=9)
    max_hour = Column(Integer, default=18)
    buffer_minutes = Column(Integer, default=60)
    
    # Relationships
    user = relationship("User", back_populates="settings")

    def as_credentials(self):
        """Convert DB tokens into a Google OAuth Credentials object."""
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes.split(",") if self.scopes else None,
        )

class AuthSessionDB(Base):
    """Temporary authentication sessions for OAuth flow"""
    __tablename__ = "auth_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    state = Column(String, nullable=False)
    code_verifier = Column(String, nullable=False)
    
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    user_email = Column(String, nullable=True)
    
    completed = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

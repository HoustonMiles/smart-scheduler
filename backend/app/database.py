from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.database_models import Base
from app.config import DATABASE_URL, ENVIRONMENT

# Create async engine with conditional settings based on database type
engine_kwargs = {
    "echo": (ENVIRONMENT != "production"),
}

# Only add pool settings for PostgreSQL (not SQLite)
if DATABASE_URL and "postgresql" in DATABASE_URL:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 5 if ENVIRONMENT == "production" else 2,
        "max_overflow": 10 if ENVIRONMENT == "production" else 5
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully!")

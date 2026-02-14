from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import tasks, scheduler, auth, settings, sync
from app.config import ORIGINS, ENVIRONMENT, log_config
from app.core.logging_config import setup_logging
from app.core.middleware import exception_handler_middleware

logger = setup_logging(ENVIRONMENT)

app = FastAPI(title="Smart Scheduler API")

# Add exception handling middleware
@app.middleware("http")
async def add_exception_handler(request, call_next):
    return await exception_handler_middleware(request, call_next)

@app.on_event("startup")
async def startup():
    logger.info("🚀 Starting Smart Scheduler API...")
    await init_db()
    logger.info("✅ Database initialized")
    log_config()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
app.include_router(auth.router, prefix="", tags=["auth"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])

logger.info("✅ Smart Scheduler API ready")

"""
Exception handling middleware for Smart Scheduler
"""
import os
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions import AppException


async def exception_handler_middleware(request: Request, call_next):
    """
    Global exception handler middleware.
    
    Catches custom AppException instances and converts them to
    proper HTTP responses.
    """
    try:
        return await call_next(request)
    except AppException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
                "detail": str(exc)
            }
        )
    except Exception as exc:
        # Log unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if os.getenv("DEBUG") else "An error occurred"
            }
        )

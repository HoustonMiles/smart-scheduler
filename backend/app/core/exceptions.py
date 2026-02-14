"""
Custom exception classes for Smart Scheduler
"""
from fastapi import HTTPException


class AppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(AppException):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class AuthorizationError(AppException):
    """Raised when user doesn't have permission"""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class ResourceNotFoundError(AppException):
    """Raised when resource is not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(AppException):
    """Raised when validation fails"""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


class CalendarNotConfiguredError(AppException):
    """Raised when Google Calendar is not configured"""
    def __init__(self, message: str = "Google Calendar not configured. Please login first."):
        super().__init__(message, status_code=400)


def create_http_exception(exc: AppException) -> HTTPException:
    """Convert AppException to HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message
    )

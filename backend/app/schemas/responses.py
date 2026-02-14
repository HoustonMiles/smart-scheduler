"""
Standard response schemas for API endpoints
"""
from pydantic import BaseModel
from typing import Optional, Any


class StandardResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Any] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": 1, "title": "Example"}
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Validation error",
                "detail": "Field 'title' is required"
            }
        }


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Task scheduled successfully"
            }
        }

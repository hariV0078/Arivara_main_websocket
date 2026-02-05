from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


class ChatbotAPIException(Exception):
    """Base exception for Chatbot API."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def chatbot_exception_handler(request: Request, exc: ChatbotAPIException):
    """Handle custom ChatbotAPIException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error": exc.details
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error",
            "error": {
                "details": errors
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "error": {
                "type": type(exc).__name__,
                "detail": str(exc) if str(exc) else "An unexpected error occurred"
            }
        }
    )

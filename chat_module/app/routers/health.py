from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "chatbot-api",
            "version": "1.0.0"
        }
    )


@router.get("/ping")
async def ping() -> JSONResponse:
    """Simple ping endpoint for testing."""
    return JSONResponse(
        status_code=200,
        content={"message": "pong"}
    )

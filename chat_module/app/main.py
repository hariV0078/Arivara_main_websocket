from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.routers import chat_router, health_router
from app.exceptions import (
    ChatbotAPIException,
    chatbot_exception_handler,
    validation_exception_handler,
    general_exception_handler
)

app = FastAPI(
    title="Chatbot Plugin API",
    description="""
    A comprehensive chatbot API service with the following features:
    
    * **Image Processing**: Upload and process images using GPT-4 Vision
    * **Web Scraping**: Automatic web search and content extraction for up-to-date information
    * **Chat History**: Manage conversations with headings and message history
    * **OpenAI Integration**: Powered by GPT-4 and GPT-4 Vision models
    
    ## Authentication
    All endpoints require JWT authentication via Supabase. Include the token in the Authorization header:
    ```
    Authorization: Bearer <your_jwt_token>
    ```
    
    ## Base URL
    All API endpoints are prefixed with `/api`
    """,
    version="1.0.0",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Chat operations - send messages, manage chats, and handle conversations"
        },
        {
            "name": "Health",
            "description": "Health check and monitoring endpoints"
        }
    ]
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(ChatbotAPIException, chatbot_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    # Close web scraper browser if open
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

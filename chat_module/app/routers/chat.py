from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from uuid import UUID
import json
from app.models.chat import ChatCreate, ChatResponse, ChatUpdate, ChatListResponse
from app.models.message import ChatMessageRequest, ChatMessageResponse, MessageResponse
from app.services.supabase_service import SupabaseService
from app.services.openai_service import OpenAIService
from app.services.image_service import ImageService
from app.services.web_scraper import WebScraperService
from app.services.pdf_service import PDFService
from app.utils.helpers import validate_jwt_token, format_error_response

router = APIRouter(prefix="/chat", tags=["Chat"])
security = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract and validate user ID from JWT token."""
    token = credentials.credentials
    payload = validate_jwt_token(token)
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: user ID not found"
        )
    return user_id


def get_services():
    """Dependency injection for services."""
    supabase_service = SupabaseService()
    openai_service = OpenAIService()
    image_service = ImageService(supabase_service)
    web_scraper = WebScraperService()
    pdf_service = PDFService()
    return {
        "supabase": supabase_service,
        "openai": openai_service,
        "image": image_service,
        "web_scraper": web_scraper,
        "pdf": pdf_service,
    }


@router.post("", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """
    Send a message to the chatbot.
    Supports text messages with optional images and web scraping.
    """
    try:
        supabase = services["supabase"]
        openai = services["openai"]
        image_service = services["image"]
        web_scraper = services["web_scraper"]
        pdf_service = services["pdf"]
        
        # Get or create chat
        chat_id = request.chat_id
        if not chat_id:
            # Create new chat
            chat_data = supabase.create_chat(UUID(user_id))
            chat_id = UUID(chat_data["id"])
        else:
            # Verify chat belongs to user
            chat = supabase.get_chat(chat_id, UUID(user_id))
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat not found"
                )
        
        # Process images if provided
        image_urls = []
        if request.images:
            # Upload images to Supabase Storage and get URLs
            image_bytes_list = image_service.process_base64_images(request.images)
            image_urls = await image_service.upload_multiple_images(image_bytes_list, user_id)
        
        # Get chat history
        existing_messages = supabase.get_chat_messages(chat_id, UUID(user_id))
        
        # Prepare messages for OpenAI
        messages = []
        for msg in existing_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "image_urls": msg.get("image_urls", [])
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": request.message,
            "image_urls": image_urls
        })
        
        # Save user message
        supabase.create_message(
            chat_id=chat_id,
            role="user",
            content=request.message,
            image_urls=image_urls
        )
        
        # Determine if web scraping is needed
        web_context = ""
        web_sources = []
        metadata = {}

        if request.enable_web_scraping and openai.should_use_web_scraping(request.message):
            web_context = await web_scraper.get_web_context(request.message, scrape_content=True)
            if web_context:
                # Extract sources from context
                import re

                source_pattern = r"Source:.*?\((https?://[^\)]+)\)"
                web_sources = re.findall(source_pattern, web_context)
                metadata["web_scraping_used"] = True
                metadata["sources"] = web_sources

        # Extract text from PDFs if provided
        pdf_context = ""
        if request.pdf_urls:
            pdf_context = await pdf_service.fetch_and_extract_text(request.pdf_urls)
            if pdf_context:
                metadata["pdfs_used"] = request.pdf_urls

        # Generate response (Gemini or OpenAI)
        response_content = await openai.generate_response(
            messages=messages,
            images=None,  # Images are already in messages as image_urls
            web_context=web_context if web_context else None,
            pdf_context=pdf_context if pdf_context else None,
        )
        
        # Save assistant message
        supabase.create_message(
            chat_id=chat_id,
            role="assistant",
            content=response_content,
            metadata=metadata
        )
        
        # Auto-generate heading if this is the first message
        if len(existing_messages) == 0:
            try:
                heading = await openai.generate_heading(request.message)
                supabase.update_chat_heading(chat_id, UUID(user_id), heading)
            except Exception as e:
                print(f"Failed to generate heading: {e}")
        
        return ChatMessageResponse(
            success=True,
            data={
                "chat_id": str(chat_id),
                "message": response_content,
                "image_urls": image_urls
            },
            message="Message processed successfully",
            metadata=metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """Upload an image and get its URL."""
    try:
        image_service = services["image"]
        
        # Read file content
        image_bytes = await file.read()
        
        # Upload to Supabase Storage
        url = await image_service.upload_image(image_bytes, user_id)
        
        return {
            "success": True,
            "data": {"url": url},
            "message": "Image uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading image: {str(e)}"
        )


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """List all chats for the authenticated user."""
    try:
        supabase = services["supabase"]
        result = supabase.get_user_chats(UUID(user_id), page, page_size)
        
        return ChatListResponse(
            success=True,
            data=[ChatResponse(**chat) for chat in result["data"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving chats: {str(e)}"
        )


@router.get("/chats/{chat_id}")
async def get_chat(
    chat_id: UUID,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """Get a specific chat with all its messages."""
    try:
        supabase = services["supabase"]
        chat = supabase.get_chat_with_messages(chat_id, UUID(user_id))
        
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        return {
            "success": True,
            "data": {
                "chat": ChatResponse(**{k: v for k, v in chat.items() if k != "messages"}),
                "messages": [MessageResponse(**msg) for msg in chat.get("messages", [])]
            },
            "message": "Chat retrieved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving chat: {str(e)}"
        )


@router.get("/chats/by-heading/{heading}")
async def get_chat_by_heading(
    heading: str,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """
    Get a chat by heading (partial match, case-insensitive).
    Returns the first matching chat with all its messages.
    """
    try:
        supabase = services["supabase"]
        chat = supabase.get_chat_by_heading(heading, UUID(user_id))
        
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat with heading containing '{heading}' not found"
            )
        
        return {
            "success": True,
            "data": {
                "chat": ChatResponse(**{k: v for k, v in chat.items() if k != "messages"}),
                "messages": [MessageResponse(**msg) for msg in chat.get("messages", [])]
            },
            "message": "Chat retrieved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving chat: {str(e)}"
        )


@router.get("/chats/search/heading")
async def search_chats_by_heading(
    q: str,
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """
    Search chats by heading (partial match, case-insensitive).
    Returns a list of matching chats with pagination.
    """
    try:
        supabase = services["supabase"]
        result = supabase.search_chats_by_heading(q, UUID(user_id), page, page_size)
        
        return ChatListResponse(
            success=True,
            data=[ChatResponse(**chat) for chat in result["data"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            message=f"Found {result['total']} chat(s) matching '{q}'"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching chats: {str(e)}"
        )


@router.post("/chats", response_model=ChatResponse)
async def create_chat(
    request: ChatCreate,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """Create a new chat."""
    try:
        supabase = services["supabase"]
        openai = services["openai"]
        
        heading = request.heading
        auto_heading = None
        
        if request.auto_generate_heading and not heading:
            # This will be generated after first message, so just create chat
            pass
        
        chat_data = supabase.create_chat(UUID(user_id), heading, auto_heading)
        
        return ChatResponse(**chat_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating chat: {str(e)}"
        )


@router.put("/chats/{chat_id}/heading", response_model=ChatResponse)
async def update_chat_heading(
    chat_id: UUID,
    request: ChatUpdate,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """Update chat heading."""
    try:
        supabase = services["supabase"]
        chat_data = supabase.update_chat_heading(chat_id, UUID(user_id), request.heading)
        
        if not chat_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        return ChatResponse(**chat_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating chat heading: {str(e)}"
        )


@router.delete("/chats/{chat_id}")
async def delete_chat(
    chat_id: UUID,
    user_id: str = Depends(get_user_id),
    services: dict = Depends(get_services)
):
    """Delete a chat and all its messages."""
    try:
        supabase = services["supabase"]
        success = supabase.delete_chat(chat_id, UUID(user_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        return {
            "success": True,
            "message": "Chat deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting chat: {str(e)}"
        )

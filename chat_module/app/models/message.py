from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class MessageCreate(BaseModel):
    chat_id: UUID
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    image_urls: Optional[List[str]] = None
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    id: UUID
    chat_id: UUID
    role: str
    content: str
    image_urls: Optional[List[str]] = None
    metadata: Optional[dict] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    chat_id: Optional[UUID] = None
    message: str = Field(..., min_length=1, max_length=10000, description="The message content")
    images: Optional[List[str]] = Field(None, max_items=5, description="Base64 encoded images (max 5)")
    pdf_urls: Optional[List[str]] = Field(
        None,
        max_items=5,
        description="URLs of PDFs (e.g., Supabase public URLs) to include as context",
    )
    enable_web_scraping: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Summarize the attached PDFs and current news on AI.",
                "images": None,
                "pdf_urls": [
                    "https://your-supabase-url.supabase.co/storage/v1/object/public/chatbot-pdfs/user-id/report.pdf"
                ],
                "enable_web_scraping": True,
            }
        }


class ChatMessageResponse(BaseModel):
    success: bool = True
    data: dict
    message: str = "Message processed successfully"
    metadata: Optional[dict] = None

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class ChatCreate(BaseModel):
    heading: Optional[str] = Field(None, max_length=100, description="User-provided chat heading")
    auto_generate_heading: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "heading": "Weather Discussion",
                "auto_generate_heading": False
            }
        }


class ChatUpdate(BaseModel):
    heading: Optional[str] = Field(None, max_length=100, description="New chat heading")


class ChatResponse(BaseModel):
    id: UUID
    user_id: UUID
    heading: Optional[str] = None
    auto_heading: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    success: bool = True
    data: list[ChatResponse]
    total: int
    page: int = 1
    page_size: int = 20
    message: str = "Chats retrieved successfully"

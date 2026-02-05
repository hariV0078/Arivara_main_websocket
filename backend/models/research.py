"""Research history and document Pydantic models."""

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


class ResearchHistoryCreate(BaseModel):
    """Model for creating a research history entry."""
    user_id: UUID
    query: str
    report_type: str
    credits_used: int
    status: str = "pending"


class ResearchHistoryUpdate(BaseModel):
    """Model for updating a research history entry."""
    status: Optional[Literal["pending", "completed", "failed"]] = None
    result_summary: Optional[str] = None
    credits_used: Optional[int] = None
    completed_at: Optional[datetime] = None


class ResearchHistory(BaseModel):
    """Complete research history model."""
    id: UUID
    user_id: UUID
    query: str
    report_type: str
    credits_used: int
    status: Literal["pending", "completed", "failed"]
    result_summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ResearchDocumentCreate(BaseModel):
    """Model for creating a research document entry."""
    research_id: UUID
    file_name: str
    file_path: str
    file_type: Literal["pdf", "docx", "markdown"]
    file_size: Optional[int] = None


class ResearchDocument(BaseModel):
    """Complete research document model."""
    id: UUID
    research_id: UUID
    file_name: str
    file_path: str
    file_type: Literal["pdf", "docx", "markdown"]
    file_size: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


"""User profile Pydantic models."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserProfileBase(BaseModel):
    """Base user profile model."""
    email: EmailStr
    full_name: Optional[str] = None
    credits: int = 100


class UserProfileCreate(UserProfileBase):
    """Model for creating a user profile."""
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None


class UserProfileUpdate(BaseModel):
    """Model for updating a user profile."""
    full_name: Optional[str] = None
    credits: Optional[int] = None


class UserProfile(UserProfileBase):
    """Complete user profile model."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


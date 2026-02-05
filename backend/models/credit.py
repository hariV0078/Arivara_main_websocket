"""Credit transaction Pydantic models."""

from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from uuid import UUID


class CreditTransactionCreate(BaseModel):
    """Model for creating a credit transaction."""
    user_id: UUID
    amount: int
    transaction_type: Literal["debit", "credit"]
    description: str
    balance_after: int


class CreditTransaction(BaseModel):
    """Complete credit transaction model."""
    id: UUID
    user_id: UUID
    amount: int
    transaction_type: Literal["debit", "credit"]
    description: str
    balance_after: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreditBalance(BaseModel):
    """User credit balance model."""
    user_id: UUID
    balance: int
    last_updated: datetime


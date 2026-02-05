"""Credit management service."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from supabase import Client
import logging
from ..auth.supabase_client import get_service_client
from ..models.credit import CreditTransaction, CreditTransactionCreate

logger = logging.getLogger(__name__)

# Credit calculation constants
BASE_COST = 10
REPORT_TYPE_MULTIPLIERS = {
    "research_report": 1.0,
    "resource_report": 1.0,
    "outline_report": 0.8,
    "custom_report": 1.2,
    "detailed_report": 2.0,
    "subtopic_report": 1.5,
    "deep": 3.0,
    "multi_agents": 2.5,
    "quick_summary": 0.5,
    "comprehensive_analysis": 3.0,
}

# Token-based credit calculation: 1 million tokens = 4500 credits
TOKENS_PER_MILLION = 1_000_000
CREDITS_PER_MILLION_TOKENS = 4500


class CreditService:
    """Service for managing user credits."""
    
    def __init__(self, client: Optional[Client] = None):
        """
        Initialize CreditService.
        
        Args:
            client: Optional Supabase client (uses service client by default)
        """
        self.client = client or get_service_client()
    
    def calculate_research_cost(self, report_type: str, query_length: int) -> int:
        """
        Calculate estimated cost for a research request.
        
        Args:
            report_type: Type of report to generate
            query_length: Length of the query string
            
        Returns:
            Estimated credit cost
        """
        base = BASE_COST
        type_multiplier = REPORT_TYPE_MULTIPLIERS.get(report_type, 1.0)
        length_multiplier = 1 + (query_length / 500)  # Add 1 credit per 500 chars
        
        cost = int(base * type_multiplier * length_multiplier)
        return max(1, cost)  # Minimum 1 credit
    
    def calculate_credits_from_tokens(self, total_tokens: int) -> int:
        """
        Calculate credits from token usage.
        Formula: 1 million tokens = 4500 credits
        
        Args:
            total_tokens: Total number of tokens used
            
        Returns:
            Credits to charge (minimum 1)
        """
        if total_tokens <= 0:
            return 1
        credits = (total_tokens / TOKENS_PER_MILLION) * CREDITS_PER_MILLION_TOKENS
        return max(1, int(credits + 0.5))  # Round to nearest integer, minimum 1
    
    def calculate_credits_from_token_usage(self, token_usage: dict) -> int:
        """
        Calculate credits from token usage dictionary.
        Formula: 1 million tokens = 4500 credits
        
        Args:
            token_usage: Dictionary with token usage information
                Expected keys: 'total_tokens', 'total_prompt_tokens', 'total_completion_tokens'
                Or: 'prompt_tokens', 'completion_tokens'
                
        Returns:
            Credits to charge (minimum 1)
        """
        total_tokens = token_usage.get('total_tokens', 0)
        if total_tokens == 0:
            # Try to calculate from prompt and completion tokens
            prompt_tokens = token_usage.get('total_prompt_tokens', token_usage.get('prompt_tokens', 0))
            completion_tokens = token_usage.get('total_completion_tokens', token_usage.get('completion_tokens', 0))
            total_tokens = prompt_tokens + completion_tokens
        return self.calculate_credits_from_tokens(total_tokens)
    
    async def get_credit_balance(self, user_id: UUID) -> int:
        """
        Get user's current credit balance.
        
        Args:
            user_id: User UUID
            
        Returns:
            Current credit balance
        """
        try:
            result = self.client.table("user_profiles").select("credits").eq("id", str(user_id)).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("credits", 0)
            return 0
            
        except Exception as e:
            logger.error(f"Error getting credit balance: {e}")
            return 0
    
    async def deduct_credits(
        self, 
        user_id: UUID, 
        amount: int, 
        description: str
    ) -> bool:
        """
        Deduct credits from user account.
        
        Args:
            user_id: User UUID
            amount: Amount to deduct
            description: Transaction description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current balance
            current_balance = await self.get_credit_balance(user_id)
            
            if current_balance < amount:
                logger.warning(f"Insufficient credits for user {user_id}: {current_balance} < {amount}")
                return False
            
            new_balance = current_balance - amount
            
            # Update user profile
            self.client.table("user_profiles").update({
                "credits": new_balance,
                "updated_at": "now()"
            }).eq("id", str(user_id)).execute()
            
            # Create transaction record
            transaction = CreditTransactionCreate(
                user_id=user_id,
                amount=amount,
                transaction_type="debit",
                description=description,
                balance_after=new_balance
            )
            
            # Convert UUID to string for JSON serialization
            transaction_dict = transaction.dict()
            transaction_dict['user_id'] = str(transaction_dict['user_id'])
            self.client.table("credit_transactions").insert(transaction_dict).execute()
            
            logger.info(f"Deducted {amount} credits from user {user_id}. New balance: {new_balance}")
            return True
            
        except Exception as e:
            logger.error(f"Error deducting credits: {e}")
            return False
    
    async def add_credits(
        self, 
        user_id: UUID, 
        amount: int, 
        description: str
    ) -> bool:
        """
        Add credits to user account.
        
        Args:
            user_id: User UUID
            amount: Amount to add
            description: Transaction description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current balance
            current_balance = await self.get_credit_balance(user_id)
            new_balance = current_balance + amount
            
            # Update user profile
            self.client.table("user_profiles").update({
                "credits": new_balance,
                "updated_at": "now()"
            }).eq("id", str(user_id)).execute()
            
            # Create transaction record
            transaction = CreditTransactionCreate(
                user_id=user_id,
                amount=amount,
                transaction_type="credit",
                description=description,
                balance_after=new_balance
            )
            
            # Convert UUID to string for JSON serialization
            transaction_dict = transaction.dict()
            transaction_dict['user_id'] = str(transaction_dict['user_id'])
            self.client.table("credit_transactions").insert(transaction_dict).execute()
            
            logger.info(f"Added {amount} credits to user {user_id}. New balance: {new_balance}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding credits: {e}", exc_info=True)
            return False
    
    async def set_credits(
        self,
        user_id: UUID,
        amount: int,
        description: str
    ) -> bool:
        """
        Set credits to a specific amount (directly set balance).
        
        Args:
            user_id: User UUID
            amount: Target credit balance
            description: Transaction description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current balance
            current_balance = await self.get_credit_balance(user_id)
            
            # Calculate the difference
            difference = amount - current_balance
            transaction_type = "credit" if difference >= 0 else "debit"
            transaction_amount = abs(difference)
            
            # Update user profile (upsert to handle case where profile doesn't exist)
            result = self.client.table("user_profiles").update({
                "credits": amount,
                "updated_at": "now()"
            }).eq("id", str(user_id)).execute()
            
            # If no rows were updated, the profile might not exist - try to insert
            if not result.data:
                # Try to upsert (this will insert if doesn't exist, update if exists)
                self.client.table("user_profiles").upsert({
                    "id": str(user_id),
                    "credits": amount,
                    "updated_at": "now()"
                }).execute()
            
            # Create transaction record only if there's a change
            if difference != 0:
                transaction = CreditTransactionCreate(
                    user_id=user_id,
                    amount=transaction_amount,
                    transaction_type=transaction_type,
                    description=description,
                    balance_after=amount
                )
                
                # Convert UUID to string for JSON serialization
                transaction_dict = transaction.dict()
                transaction_dict['user_id'] = str(transaction_dict['user_id'])
                self.client.table("credit_transactions").insert(transaction_dict).execute()
            
            logger.info(f"Set credits for user {user_id} to {amount} (was {current_balance})")
            return True
            
        except Exception as e:
            logger.error(f"Error setting credits: {e}", exc_info=True)
            return False
    
    async def get_credit_history(
        self, 
        user_id: UUID, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user's credit transaction history.
        
        Args:
            user_id: User UUID
            limit: Maximum number of transactions to return
            
        Returns:
            List of transaction dictionaries
        """
        try:
            result = (
                self.client.table("credit_transactions")
                .select("*")
                .eq("user_id", str(user_id))
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting credit history: {e}")
            return []


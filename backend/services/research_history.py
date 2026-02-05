"""Research history tracking service."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from supabase import Client
import logging
from ..auth.supabase_client import get_service_client
from ..models.research import ResearchHistory, ResearchHistoryCreate, ResearchHistoryUpdate

logger = logging.getLogger(__name__)


class ResearchHistoryService:
    """Service for managing research history."""
    
    def __init__(self, client: Optional[Client] = None):
        """
        Initialize ResearchHistoryService.
        
        Args:
            client: Optional Supabase client (uses service client by default)
        """
        self.client = client or get_service_client()
    
    async def create_research_entry(
        self,
        user_id: UUID,
        query: str,
        report_type: str,
        credits_used: int
    ) -> Optional[UUID]:
        """
        Create a new research history entry.
        
        Args:
            user_id: User UUID
            query: Research query
            report_type: Type of report
            credits_used: Credits used for this research (can be 0 initially)
            
        Returns:
            Research ID (UUID) if successful, None otherwise
        """
        try:
            # Prepare entry data
            entry_data = {
                "user_id": str(user_id),
                "query": query,
                "report_type": report_type,
                "credits_used": credits_used,  # Can be 0 initially, will be updated on completion
                "status": "pending"
            }
            
            logger.debug(f"Attempting to create research entry with data: {entry_data}")
            
            result = self.client.table("research_history").insert(entry_data).execute()
            
            if result.data and len(result.data) > 0:
                research_id = UUID(result.data[0]["id"])
                logger.info(f"Created research entry {research_id} for user {user_id}")
                return research_id
            else:
                logger.warning(f"Insert succeeded but no data returned for user {user_id}")
                return None
            
        except Exception as e:
            error_msg = str(e)
            error_dict = {}
            if hasattr(e, '__dict__'):
                error_dict = e.__dict__
            elif isinstance(e, dict):
                error_dict = e
            
            # Try to extract error code and message from Supabase error
            error_code = str(error_dict.get("code", ""))
            error_message = error_dict.get("message", error_msg)
            error_details = error_dict.get("details", "")
            error_hint = error_dict.get("hint", "")
            
            logger.error(f"Error creating research entry for user {user_id}: {e}", exc_info=True)
            logger.error(f"Error code: {error_code}, Message: {error_message}")
            if error_details:
                logger.error(f"Error details: {error_details}")
            if error_hint:
                logger.error(f"Error hint: {error_hint}")
            
            # Check for specific error types
            if "foreign key constraint" in error_msg.lower() or "23503" in error_code:
                logger.error(
                    f"FOREIGN KEY CONSTRAINT VIOLATION - user_id {user_id} may not exist in user_profiles table. "
                    f"This is the most likely cause. Error: {error_message}"
                )
            elif "relation" in error_msg.lower() or "does not exist" in error_msg.lower() or "pgrst205" in error_msg.lower():
                logger.error("Research history table may not exist. Run: python -m backend.database.setup_schema")
            elif "permission denied" in error_msg.lower() or "row-level security" in error_msg.lower() or "42501" in error_code:
                logger.error("RLS policy may be blocking insert. Check Supabase RLS policies for research_history table.")
            elif "409" in error_msg or "conflict" in error_msg.lower():
                logger.warning(f"409 Conflict when creating research entry - may be a duplicate: {error_message}")
            elif "not null" in error_msg.lower() or "null value" in error_msg.lower():
                logger.error(f"NOT NULL constraint violation: {error_message}")
            else:
                logger.error(f"Unknown error creating research entry. Full error: {error_msg}")
            
            return None
    
    async def update_research_status(
        self,
        research_id: UUID,
        status: str,
        result_summary: Optional[str] = None,
        credits_used: Optional[int] = None,
        token_usage: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update research status and completion info.
        
        Args:
            research_id: Research UUID
            status: New status (pending, completed, failed)
            result_summary: Optional summary of results
            credits_used: Optional actual credits used
            token_usage: Optional token usage dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            update_data: Dict[str, Any] = {
                "status": status,
            }
            
            if result_summary:
                update_data["result_summary"] = result_summary
            
            if credits_used is not None:
                update_data["credits_used"] = credits_used
            
            if token_usage is not None:
                update_data["token_usage"] = token_usage
            
            if status == "completed" or status == "failed":
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            result = (
                self.client.table("research_history")
                .update(update_data)
                .eq("id", str(research_id))
                .execute()
            )
            
            if result.data:
                logger.info(f"Updated research {research_id} status to {status}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating research status: {e}")
            return False
    
    async def get_user_research_history(
        self,
        user_id: UUID,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user's research history.
        
        Args:
            user_id: User UUID
            limit: Maximum number of entries to return
            
        Returns:
            List of research history dictionaries
        """
        try:
            result = (
                self.client.table("research_history")
                .select("*")
                .eq("user_id", str(user_id))
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting research history: {e}")
            return []
    
    async def get_research_by_id(
        self,
        research_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get research entry by ID.
        
        Args:
            research_id: Research UUID
            
        Returns:
            Research history dictionary or None
        """
        try:
            result = (
                self.client.table("research_history")
                .select("*")
                .eq("id", str(research_id))
                .execute()
            )
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting research by ID: {e}")
            return None


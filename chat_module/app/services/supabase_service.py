from supabase import Client
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from app.config import settings

# Import backend's Supabase client to use the same instance
try:
    import sys
    import os
    # Add backend to path if not already there
    backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from auth.supabase_client import get_service_client
    USE_BACKEND_CLIENT = True
except ImportError:
    # Fallback to creating own client if backend not available
    from supabase import create_client
    USE_BACKEND_CLIENT = False


class SupabaseService:
    def __init__(self):
        if USE_BACKEND_CLIENT:
            # Use the same Supabase client instance as the main backend
            self.client: Client = get_service_client()
        else:
            # Fallback: create own client (for standalone mode)
            self.client: Client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
    
    def create_chat(self, user_id: UUID, heading: Optional[str] = None, auto_heading: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat."""
        data = {
            "user_id": str(user_id),
            "heading": heading,
            "auto_heading": auto_heading,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.client.table("chats").insert(data).execute()
        return result.data[0] if result.data else None
    
    def get_chat(self, chat_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a chat by ID for a specific user."""
        result = self.client.table("chats").select("*").eq("id", str(chat_id)).eq("user_id", str(user_id)).execute()
        return result.data[0] if result.data else None
    
    def get_user_chats(self, user_id: UUID, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get all chats for a user with pagination."""
        offset = (page - 1) * page_size
        result = self.client.table("chats").select("*").eq("user_id", str(user_id)).order("updated_at", desc=True).range(offset, offset + page_size - 1).execute()
        
        # Get total count
        count_result = self.client.table("chats").select("id", count="exact").eq("user_id", str(user_id)).execute()
        total = count_result.count if hasattr(count_result, 'count') else len(result.data)
        
        return {
            "data": result.data or [],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    def update_chat_heading(self, chat_id: UUID, user_id: UUID, heading: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update chat heading."""
        data = {
            "heading": heading,
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.client.table("chats").update(data).eq("id", str(chat_id)).eq("user_id", str(user_id)).execute()
        return result.data[0] if result.data else None
    
    def delete_chat(self, chat_id: UUID, user_id: UUID) -> bool:
        """Delete a chat and all its messages."""
        # Delete messages first (cascade should handle this, but being explicit)
        self.client.table("messages").delete().eq("chat_id", str(chat_id)).execute()
        
        # Delete chat
        result = self.client.table("chats").delete().eq("id", str(chat_id)).eq("user_id", str(user_id)).execute()
        return len(result.data) > 0
    
    def create_message(self, chat_id: UUID, role: str, content: str, image_urls: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new message."""
        data = {
            "chat_id": str(chat_id),
            "role": role,
            "content": content,
            "image_urls": image_urls or [],
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat()
        }
        result = self.client.table("messages").insert(data).execute()
        return result.data[0] if result.data else None
    
    def get_chat_messages(self, chat_id: UUID, user_id: UUID) -> List[Dict[str, Any]]:
        """Get all messages for a chat (verify chat belongs to user)."""
        # First verify chat belongs to user
        chat = self.get_chat(chat_id, user_id)
        if not chat:
            return []
        
        result = self.client.table("messages").select("*").eq("chat_id", str(chat_id)).order("created_at", desc=False).execute()
        return result.data or []
    
    def get_chat_with_messages(self, chat_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get chat with all its messages."""
        chat = self.get_chat(chat_id, user_id)
        if not chat:
            return None
        
        messages = self.get_chat_messages(chat_id, user_id)
        chat["messages"] = messages
        return chat
    
    def get_chat_by_heading(self, heading: str, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a chat by heading for a specific user."""
        # Search for chat with matching heading (case-insensitive partial match)
        result = self.client.table("chats").select("*").eq("user_id", str(user_id)).ilike("heading", f"%{heading}%").limit(1).execute()
        
        if result.data and len(result.data) > 0:
            chat = result.data[0]
            # Get messages for this chat
            messages = self.get_chat_messages(UUID(chat["id"]), user_id)
            chat["messages"] = messages
            return chat
        
        return None
    
    def search_chats_by_heading(self, search_term: str, user_id: UUID, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Search chats by heading with pagination."""
        offset = (page - 1) * page_size
        
        # Search for chats with matching heading (case-insensitive partial match)
        result = self.client.table("chats").select("*").eq("user_id", str(user_id)).ilike("heading", f"%{search_term}%").order("updated_at", desc=True).range(offset, offset + page_size - 1).execute()
        
        # Get total count
        count_result = self.client.table("chats").select("id", count="exact").eq("user_id", str(user_id)).ilike("heading", f"%{search_term}%").execute()
        total = count_result.count if hasattr(count_result, 'count') else len(result.data)
        
        return {
            "data": result.data or [],
            "total": total,
            "page": page,
            "page_size": page_size
        }

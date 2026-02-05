"""Supabase client initialization and token verification.

Simplified implementation following Supabase official documentation.
"""

import os
from typing import Optional, Dict, Any
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# Global clients (singleton pattern)
_anon_client: Optional[Client] = None
_service_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create the Supabase anonymous client (for user operations).
    
    Uses SUPABASE_URL and SUPABASE_ANON_KEY from environment variables.
    """
    global _anon_client
    if _anon_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables"
            )
        
        _anon_client = create_client(supabase_url, supabase_key)
        logger.info("Supabase anonymous client initialized")
    
    return _anon_client


def get_service_client() -> Client:
    """
    Get or create the Supabase service role client (bypasses RLS).
    
    Uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment variables.
    WARNING: Service role key bypasses Row Level Security - use only for admin operations.
    """
    global _service_client
    if _service_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_service_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables"
            )
        
        _service_client = create_client(supabase_url, supabase_service_key)
        logger.info("Supabase service role client initialized")
    
    return _service_client


async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify JWT access token using Supabase's built-in verification.
    
    This uses Supabase's official get_user() method which automatically
    verifies the token signature and expiration.
    
    Args:
        token: JWT access token from Supabase Auth
        
    Returns:
        Dictionary with user info (id, email, user_metadata) if valid, None otherwise
        
    Example:
        >>> user = await verify_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        >>> if user:
        ...     print(f"User ID: {user['id']}")
    """
    try:
        # Use Supabase client to verify token (official method)
        client = get_supabase_client()
        response = client.auth.get_user(token)
        
        if response and response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "user_metadata": response.user.user_metadata or {},
            }
        
        return None
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


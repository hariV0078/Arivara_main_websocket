"""Authentication module for Supabase integration."""

from .supabase_client import get_supabase_client, get_service_client, verify_token
from .auth_middleware import authenticate_websocket, require_auth
from .user_manager import UserManager

__all__ = [
    "get_supabase_client",
    "get_service_client",
    "verify_token",
    "authenticate_websocket",
    "require_auth",
    "UserManager",
]


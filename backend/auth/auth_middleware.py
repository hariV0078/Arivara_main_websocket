"""WebSocket authentication middleware."""

from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import logging
from .supabase_client import verify_token

logger = logging.getLogger(__name__)

# Store authenticated user IDs per WebSocket connection
_websocket_users: Dict[WebSocket, str] = {}


async def authenticate_websocket(websocket: WebSocket, token: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate WebSocket connection using JWT token.
    
    Args:
        websocket: WebSocket connection
        token: JWT token string
        
    Returns:
        User dictionary if authenticated, None otherwise
    """
    try:
        user = await verify_token(token)
        if user:
            _websocket_users[websocket] = user["id"]
            logger.info(f"WebSocket authenticated for user: {user['id']}")
            return user
        else:
            logger.warning("WebSocket authentication failed: invalid token")
            return None
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


def get_websocket_user_id(websocket: WebSocket) -> Optional[str]:
    """
    Get user ID associated with WebSocket connection.
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        User ID if authenticated, None otherwise
    """
    return _websocket_users.get(websocket)


def set_websocket_user_id(websocket: WebSocket, user_id: str) -> None:
    """
    Associate user ID with WebSocket connection.
    
    Args:
        websocket: WebSocket connection
        user_id: User ID string
    """
    _websocket_users[websocket] = user_id


def remove_websocket_user(websocket: WebSocket) -> None:
    """
    Remove user association from WebSocket connection.
    
    Args:
        websocket: WebSocket connection
    """
    _websocket_users.pop(websocket, None)


async def require_auth(websocket: WebSocket) -> str:
    """
    Require authentication for WebSocket operation.
    Raises exception if not authenticated.
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        User ID string
        
    Raises:
        WebSocketDisconnect: If not authenticated
    """
    user_id = get_websocket_user_id(websocket)
    if not user_id:
        await websocket.send_json({
            "type": "error",
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Authentication required. Please send 'authenticate' message first."
        })
        raise WebSocketDisconnect(code=1008, reason="Authentication required")
    return user_id


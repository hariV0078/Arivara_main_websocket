import base64
import io
from PIL import Image
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import asyncio

# Try to use backend's verify_token for consistent authentication
try:
    import sys
    import os
    # Add backend to path if not already there
    backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from auth.supabase_client import verify_token as backend_verify_token
    USE_BACKEND_AUTH = True
except ImportError:
    # Fallback to manual validation if backend not available
    from jose import JWTError, jwt
    from app.config import settings
    USE_BACKEND_AUTH = False


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token from Supabase.
    Uses backend's verify_token for consistent authentication.
    Returns decoded token payload if valid.
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        if USE_BACKEND_AUTH:
            # Use backend's verify_token (async, so we need to run it)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            user = loop.run_until_complete(backend_verify_token(token))
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token"
                )
            
            # Return payload in expected format
            return {
                "sub": user.get("id"),
                "user_id": user.get("id"),
                "email": user.get("email"),
                **user.get("user_metadata", {})
            }
        else:
            # Fallback: manual validation (for standalone mode)
            import json
            import time
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            # Decode the payload (second part of JWT)
            payload_part = parts[1]
            # Add padding if needed for base64 decoding
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += '=' * padding
            payload_data = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(payload_data)
            
            # Verify the issuer is from Supabase
            expected_issuer = settings.supabase_url.rstrip('/') + '/auth/v1'
            if payload.get("iss") != expected_issuer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer"
                )
            
            # Check token hasn't expired
            if payload.get("exp", 0) < time.time():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )


def decode_base64_image(image_base64: str) -> bytes:
    """
    Decode base64 encoded image string to bytes.
    Handles data URL format (data:image/...;base64,...)
    """
    try:
        # Remove data URL prefix if present
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        image_bytes = base64.b64decode(image_base64)
        
        # Validate it's actually an image
        Image.open(io.BytesIO(image_bytes))
        
        return image_bytes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format: {str(e)}"
        )


def format_error_response(
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Format standardized error response.
    """
    error_detail = {
        "success": False,
        "message": message,
        "error": details or {}
    }
    return HTTPException(status_code=status_code, detail=error_detail)

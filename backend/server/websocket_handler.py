"""Enhanced WebSocket handler with authentication and user management."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect

from ..auth.auth_middleware import (
    authenticate_websocket,
    get_websocket_user_id,
    remove_websocket_user,
    require_auth
)
from ..auth.user_manager import UserManager
from ..services.credit_service import CreditService
from ..services.research_history import ResearchHistoryService
from ..services.document_storage import DocumentStorageService
from .websocket_manager import WebSocketManager
from .server_utils import handle_start_command, handle_chat, handle_human_feedback

logger = logging.getLogger(__name__)


class AuthenticatedWebSocketHandler:
    """Enhanced WebSocket handler with authentication and user management."""
    
    def __init__(self, manager: WebSocketManager):
        """
        Initialize handler.
        
        Args:
            manager: WebSocketManager instance
        """
        self.manager = manager
        self.user_manager = UserManager()
        self.credit_service = CreditService()
        self.research_history_service = ResearchHistoryService()
        self.document_storage_service = DocumentStorageService()
    
    async def handle_message(self, websocket: WebSocket, message: str) -> None:
        """
        Handle incoming WebSocket message.
        
        Args:
            websocket: WebSocket connection
            message: Message string
        """
        try:
            # Handle ping/pong
            if message == "ping":
                await websocket.send_text("pong")
                return
            
            # Parse JSON message
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # Handle legacy "start " prefix format
                if message.startswith("start "):
                    await self._handle_legacy_start(websocket, message)
                    return
                elif message.startswith("chat"):
                    await self._handle_legacy_chat(websocket, message)
                    return
                elif message.startswith("human_feedback"):
                    await self._handle_legacy_human_feedback(websocket, message)
                    return
                else:
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_MESSAGE",
                        "message": "Invalid message format"
                    })
                    return
            
            message_type = data.get("type")
            
            # Route message based on type
            if message_type == "create_user" or message_type == "signup":
                await self._handle_create_user(websocket, data)
            elif message_type == "authenticate":
                await self._handle_authenticate(websocket, data)
            elif message_type == "get_user_info":
                await self._handle_get_user_info(websocket)
            elif message_type == "get_credits":
                await self._handle_get_credits(websocket)
            elif message_type == "get_history":
                await self._handle_get_history(websocket, data)
            elif message_type == "get_documents":
                await self._handle_get_documents(websocket, data)
            elif message_type == "start_research":
                await self._handle_start_research(websocket, data)
            elif message_type == "chat":
                await self._handle_chat(websocket, data)
            elif message_type == "human_feedback":
                await self._handle_human_feedback(websocket, data)
            elif message_type == "resend_email_verification":
                await self._handle_resend_email_verification(websocket, data)
            elif message_type == "request_password_reset":
                await self._handle_request_password_reset(websocket, data)
            elif message_type == "reset_password":
                await self._handle_reset_password(websocket, data)
            elif message_type == "update_credits":
                await self._handle_update_credits(websocket, data)
            elif message_type == "user_chat":
                await self._handle_user_chat(websocket, data)
            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": f"Unknown message type: {message_type}"
                })
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred"
            })
    
    async def _handle_create_user(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle user creation/signup message."""
        email = data.get("email")
        password = data.get("password")
        full_name = data.get("full_name")
        
        if not email or not password:
            await websocket.send_json({
                "type": "create_user_response",
                "success": False,
                "error": "Email and password are required"
            })
            return
        
        try:
            from ..auth.supabase_client import get_supabase_client
            
            # Create user in Supabase Auth
            client = get_supabase_client()
            response = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name
                    }
                }
            })
            
            if response.user:
                user_id = response.user.id
                user_email = response.user.email
                
                # Create user profile
                profile = await self.user_manager.create_user_profile(
                    user_id,
                    user_email,
                    full_name
                )
                
                # Get access token - try from sign_up response first, then sign in
                access_token = None
                
                # Check if sign_up returned a session with token
                if response.session and response.session.access_token:
                    access_token = response.session.access_token
                    logger.info(f"Access token obtained from sign_up response for user {user_id}")
                else:
                    # If no session (email confirmation required), sign in to get token
                    logger.info(f"No session in sign_up response, attempting sign in for {email}")
                    try:
                        sign_in_response = client.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        if sign_in_response.session and sign_in_response.session.access_token:
                            access_token = sign_in_response.session.access_token
                            logger.info(f"Access token obtained from sign_in for user {user_id}")
                        else:
                            logger.warning(f"Sign in succeeded but no session/token returned for {email}")
                    except Exception as sign_in_error:
                        logger.warning(f"Sign in failed after user creation: {sign_in_error}")
                        # If sign in fails, we still created the user, but token is None
                
                await websocket.send_json({
                    "type": "create_user_response",
                    "success": True,
                    "user": {
                        "id": user_id,
                        "email": user_email,
                        "full_name": full_name,
                        "credits": profile.get("credits", 100) if profile else 100
                    },
                    "access_token": access_token,
                    "message": "User created successfully"
                })
                
                # Auto-authenticate if we have a token
                if access_token:
                    try:
                        await authenticate_websocket(websocket, access_token)
                        logger.info(f"User {user_id} auto-authenticated after creation")
                    except Exception as auth_error:
                        logger.warning(f"Auto-authentication failed: {auth_error}")
                else:
                    logger.warning(f"User {user_id} created but no access token available. Email confirmation may be required.")
            else:
                await websocket.send_json({
                    "type": "create_user_response",
                    "success": False,
                    "error": "Failed to create user"
                })
                
        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            error_msg = str(e)
            if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
                await websocket.send_json({
                    "type": "create_user_response",
                    "success": False,
                    "error": "User with this email already exists"
                })
            else:
                await websocket.send_json({
                    "type": "create_user_response",
                    "success": False,
                    "error": f"Failed to create user: {error_msg}"
                })
    
    async def _handle_authenticate(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle authentication message.
        
        Supports two formats:
        1. {"type": "authenticate", "token": "jwt-token"}
        2. {"type": "authenticate", "email": "user@example.com", "password": "password123"}
        """
        token = data.get("token")
        email = data.get("email")
        password = data.get("password")
        
        logger.info(f"Authenticate request - email: {email}, has_password: {bool(password)}, token: {token[:20] + '...' if token and len(token) > 20 else token}")
        
        # If email/password provided, prioritize them and sign in to get token
        if email and password:
            logger.info(f"Using email/password authentication for: {email}")
            try:
                from ..auth.supabase_client import get_supabase_client
                client = get_supabase_client()
                
                logger.info(f"Signing in user with email: {email}")
                sign_in_response = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if sign_in_response.session and sign_in_response.session.access_token:
                    token = sign_in_response.session.access_token
                    logger.info(f"Successfully obtained token for user: {email}")
                else:
                    # Even if no session, try to get token from response
                    # Some Supabase configurations might return token differently
                    if hasattr(sign_in_response, 'access_token'):
                        token = sign_in_response.access_token
                    elif hasattr(sign_in_response, 'data') and isinstance(sign_in_response.data, dict):
                        token = sign_in_response.data.get('access_token')
                    
                    if not token:
                        await websocket.send_json({
                            "type": "auth_response",
                            "success": False,
                            "error": "Failed to get access token. Email confirmation may be required.",
                            "error_code": "NO_TOKEN",
                            "requires_confirmation": True
                        })
                        return
            except Exception as e:
                logger.error(f"Error signing in user {email}: {e}", exc_info=True)
                error_msg = str(e)
                
                # Handle specific error cases
                if "Email not confirmed" in error_msg or "email not confirmed" in error_msg.lower():
                    await websocket.send_json({
                        "type": "auth_response",
                        "success": False,
                        "error": "Email not confirmed. Please check your email and click the confirmation link before signing in.",
                        "error_code": "EMAIL_NOT_CONFIRMED",
                        "requires_confirmation": True
                    })
                elif "Invalid login credentials" in error_msg or "invalid" in error_msg.lower() or "Invalid" in error_msg:
                    await websocket.send_json({
                        "type": "auth_response",
                        "success": False,
                        "error": "Invalid email or password",
                        "error_code": "INVALID_CREDENTIALS"
                    })
                elif "too many requests" in error_msg.lower() or "rate limit" in error_msg.lower():
                    await websocket.send_json({
                        "type": "auth_response",
                        "success": False,
                        "error": "Too many login attempts. Please try again later.",
                        "error_code": "RATE_LIMIT"
                    })
                else:
                    await websocket.send_json({
                        "type": "auth_response",
                        "success": False,
                        "error": f"Sign in failed: {error_msg}",
                        "error_code": "SIGN_IN_ERROR"
                    })
                return
        
        # Check if token is a placeholder or invalid (contains {{ or is empty/null)
        # This check happens AFTER we might have gotten token from email/password sign-in
        is_token_valid = token and token.strip() and not token.strip().startswith("{{") and not token.strip().endswith("}}")
        
        # Validate token is available and valid
        if not is_token_valid:
            await websocket.send_json({
                "type": "auth_response",
                "success": False,
                "error": "Token required. Provide either a valid 'token' or 'email' and 'password'"
            })
            return
        
        # Authenticate with token
        user = await authenticate_websocket(websocket, token)
        if user:
            # Ensure user profile exists
            profile = await self.user_manager.ensure_user_profile(
                UUID(user["id"]),
                user["email"],
                user.get("user_metadata", {}).get("full_name")
            )
            
            # Always return the access token in the response
            response_data = {
                "type": "auth_response",
                "success": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "credits": profile.get("credits", 0) if profile else 0,
                    "full_name": profile.get("full_name") if profile else None
                },
                "access_token": token  # Always return token in response
            }
            
            logger.info(f"Authentication successful for user: {user['email']}, token returned in response")
            await websocket.send_json(response_data)
        else:
            await websocket.send_json({
                "type": "auth_response",
                "success": False,
                "error": "Invalid or expired token"
            })
    
    async def _handle_get_user_info(self, websocket: WebSocket) -> None:
        """Handle get user info request."""
        try:
            user_id = await require_auth(websocket)
            profile = await self.user_manager.get_user_profile(UUID(user_id))
            
            if profile:
                await websocket.send_json({
                    "type": "user_info",
                    "user": profile
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "USER_NOT_FOUND",
                    "message": "User profile not found"
                })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Failed to get user info"
            })
    
    async def _handle_get_credits(self, websocket: WebSocket) -> None:
        """Handle get credits request."""
        try:
            user_id = await require_auth(websocket)
            credits = await self.credit_service.get_credit_balance(UUID(user_id))
            
            await websocket.send_json({
                "type": "credit_balance",
                "credits": credits
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error getting credits: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Failed to get credit balance"
            })
    
    async def _handle_get_history(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle get research history request."""
        try:
            user_id = await require_auth(websocket)
            limit = data.get("limit", 50)
            
            history = await self.research_history_service.get_user_research_history(
                UUID(user_id),
                limit
            )
            
            await websocket.send_json({
                "type": "research_history",
                "history": history
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Failed to get research history"
            })
    
    async def _handle_get_documents(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle get documents request."""
        try:
            user_id = await require_auth(websocket)
            research_id = data.get("research_id")
            
            if not research_id:
                await websocket.send_json({
                    "type": "error",
                    "code": "MISSING_PARAMETER",
                    "message": "research_id required"
                })
                return
            
            # Verify research belongs to user
            research = await self.research_history_service.get_research_by_id(UUID(research_id))
            if not research or research["user_id"] != user_id:
                await websocket.send_json({
                    "type": "error",
                    "code": "UNAUTHORIZED",
                    "message": "Research not found or access denied"
                })
                return
            
            documents = await self.document_storage_service.list_research_documents(UUID(research_id))
            
            await websocket.send_json({
                "type": "documents",
                "research_id": research_id,
                "documents": documents
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Failed to get documents"
            })
    
    async def _handle_start_research(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle authenticated research request."""
        try:
            user_id = await require_auth(websocket)
            user_id_uuid = UUID(user_id)
            
            query = data.get("query") or data.get("task")
            report_type = data.get("report_type", "research_report")
            
            if not query:
                await websocket.send_json({
                    "type": "error",
                    "code": "MISSING_PARAMETER",
                    "message": "query or task required"
                })
                return
            
            # Calculate estimated cost (for checking balance, but won't deduct until completion)
            estimated_cost = self.credit_service.calculate_research_cost(
                report_type,
                len(query)
            )
            
            # Ensure user profile exists (required for foreign key constraint in research_history)
            # The profile should have been created during authentication, but ensure it exists
            user_profile = await self.user_manager.get_user_profile(user_id)
            if not user_profile:
                logger.warning(f"User profile not found for {user_id}, attempting to ensure it exists")
                # Get user info to create profile - user is authenticated so we can get their email
                try:
                    # Get user email from authenticated session
                    # Since user is authenticated via require_auth, we can get their info
                    from ..auth.supabase_client import get_supabase_client
                    client = get_supabase_client()
                    
                    # Try to get user from auth (we need the token)
                    # For now, use ensure_user_profile which will try to create if missing
                    # The email should be available from the user's auth record
                    # We'll use a temporary approach - get user info if possible
                    user_profile = await self.user_manager.ensure_user_profile(
                        user_id_uuid,
                        f"user_{user_id}@temp.local",  # Temporary - should be updated
                        None
                    )
                except Exception as e:
                    logger.error(f"Failed to ensure user profile exists: {e}", exc_info=True)
                    # Continue anyway - the profile might exist but query failed
                    user_profile = await self.user_manager.get_user_profile(user_id)
            
            if not user_profile:
                logger.error(f"User profile does not exist for {user_id} - cannot create research entry")
                await websocket.send_json({
                    "type": "error",
                    "code": "USER_PROFILE_MISSING",
                    "message": "User profile not found. Please ensure your account is properly set up. Try logging out and back in."
                })
                return
            
            # Ensure user profile exists (required for foreign key constraint in research_history)
            user_profile = await self.user_manager.get_user_profile(user_id)
            if not user_profile:
                # Get user email from authenticated user info
                from ..auth.supabase_client import get_supabase_client, verify_token
                from ..auth.auth_middleware import get_websocket_user_id
                
                # Try to get user info to create profile
                # Since user is authenticated, we can get their info
                try:
                    # Get user email from user_id (we need to query Supabase auth)
                    # For now, ensure profile exists - it should have been created during auth
                    logger.warning(f"User profile not found for {user_id}, attempting to ensure it exists")
                    # The profile should exist from authentication, but if not, create it
                    # We'll use a placeholder email since we don't have direct access to auth.users
                    await self.user_manager.ensure_user_profile(
                        user_id_uuid,
                        f"user_{user_id}@placeholder.local",  # Placeholder - should be updated
                        None
                    )
                except Exception as e:
                    logger.error(f"Failed to ensure user profile exists: {e}", exc_info=True)
                
                # Verify profile was created
                user_profile = await self.user_manager.get_user_profile(user_id)
            
            # Final check - if profile still doesn't exist, we cannot proceed
            if not user_profile:
                logger.error(f"CRITICAL: User profile does not exist for {user_id} after ensure attempt")
                logger.error(f"This will cause foreign key constraint violation when creating research entry")
                await websocket.send_json({
                    "type": "error",
                    "code": "USER_PROFILE_MISSING",
                    "message": "User profile not found. This is required to start research. Please try authenticating again."
                })
                return
            
            # ============================================================================
            # CREDIT VALIDATION TEMPORARILY DISABLED
            # ============================================================================
            # Credit checking logic has been commented out per requirements.
            # The credit-related database models and fields remain intact.
            # To re-enable: uncomment the code below
            # ============================================================================
            
            # COMMENTED OUT: Credit validation/checking logic
            # user_credits = await self.credit_service.get_credit_balance(user_id_uuid)
            # if user_credits < estimated_cost:
            #     await websocket.send_json({
            #         "type": "error",
            #         "code": "INSUFFICIENT_CREDITS",
            #         "message": f"Need at least {estimated_cost} credits (estimated), have {user_credits}. Actual credits will be calculated based on token usage after completion.",
            #         "required": estimated_cost,
            #         "available": user_credits
            #     })
            #     return
            
            # Create research entry (credits set to 0 since credit logic is disabled)
            research_id = await self.research_history_service.create_research_entry(
                user_id_uuid,
                query,
                report_type,
                0  # Credits not deducted yet, will be set on completion
            )
            
            if not research_id:
                logger.error(f"Failed to create research entry for user {user_id_uuid}, query: {query[:50]}")
                
                # Check if it's a foreign key issue (user profile missing)
                user_profile_check = await self.user_manager.get_user_profile(user_id)
                if not user_profile_check:
                    logger.error(f"User profile does not exist for {user_id} - this is likely causing the FK constraint error")
                    await websocket.send_json({
                        "type": "error",
                        "code": "USER_PROFILE_MISSING",
                        "message": "User profile not found. This is required to create research entries. Please try logging out and back in, or contact support."
                    })
                else:
                    logger.error(f"Research entry creation failed despite user profile existing for {user_id}")
                    # Try to diagnose the issue by checking if we can query the table
                    try:
                        test_query = self.research_history_service.client.table("research_history").select("id").limit(1).execute()
                        logger.info("Research history table exists and is accessible")
                    except Exception as table_error:
                        logger.error(f"Cannot access research_history table: {table_error}")
                    
                    await websocket.send_json({
                        "type": "error",
                        "code": "RESEARCH_CREATION_FAILED",
                        "message": "Failed to create research entry. Check server logs for detailed error. Possible causes: database table missing, RLS policy blocking, or constraint violation."
                    })
                return
            
            # Send research started message (no credit deduction yet)
            await websocket.send_json({
                "type": "research_progress",
                "research_id": str(research_id),
                "progress": 0,
                "status": "Starting research...",
                "estimated_cost": estimated_cost,
                "message": "Credits will be deducted based on actual token usage after research completion"
            })
            
            # Convert to legacy format for existing handler
            legacy_data = f"start {json.dumps({
                'task': query,
                'report_type': report_type,
                'report_source': data.get('report_source', 'web'),
                'tone': data.get('tone', 'Objective'),
                'source_urls': data.get('source_urls', []),
                'document_urls': data.get('document_urls', []),
                'query_domains': data.get('query_domains', []),
                'headers': data.get('headers'),
                'mcp_enabled': data.get('mcp_enabled', False),
                'mcp_strategy': data.get('mcp_strategy', 'fast'),
                'mcp_configs': data.get('mcp_configs', []),
                'research_id': str(research_id),  # Pass research_id for tracking
                'user_id': user_id  # Pass user_id for tracking
            })}"
            
            # Handle research with tracking
            await self._handle_research_with_tracking(
                websocket,
                legacy_data,
                research_id,
                user_id_uuid,
                estimated_cost
            )
            
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Error starting research: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "code": "RESEARCH_FAILED",
                "message": f"Failed to start research: {str(e)}"
            })
    
    async def _handle_research_with_tracking(
        self,
        websocket: WebSocket,
        legacy_data: str,
        research_id: UUID,
        user_id: UUID,
        estimated_cost: int
    ) -> None:
        """Handle research execution with credit and status tracking.
        
        Note: Credits are now deducted only after successful completion,
        so no refund is needed if research fails.
        """
        try:
            # Wrap the existing handler to track progress
            # This will be called asynchronously
            await handle_start_command(websocket, legacy_data, self.manager)
            
            # After research completes, credits will be deducted in research_completion.py
            # If research fails, no credits are deducted (since we don't deduct upfront)
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error in research execution: {e}", exc_info=True)
            
            # Check if it's a rate limit error and send user-friendly message
            if "rate_limit" in error_str.lower() or "429" in error_str or "tokens per min" in error_str.lower() or "too large" in error_str.lower():
                error_message = "The research context is too large for the current API limits. The context has been automatically truncated. Please try again or use a more specific query."
                if "tokens per min" in error_str.lower():
                    error_message = "API rate limit exceeded: The request is too large. Please try with a more specific query or wait a moment and try again."
                
                try:
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMIT_ERROR",
                        "message": error_message,
                        "details": error_str[:500]  # Limit details length
                    })
                except:
                    pass
            
            # Update research status to failed
            # No credits to refund since we don't deduct until completion
            if research_id:
                await self.research_history_service.update_research_status(
                    research_id,
                    "failed",
                    f"Research failed: {str(e)[:200]}"  # Limit error message length
                )
    
    async def _handle_chat(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle chat message."""
        try:
            await require_auth(websocket)
            message = data.get("message")
            if message:
                await self.manager.chat(message, websocket)
        except WebSocketDisconnect:
            raise
    
    async def _handle_human_feedback(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle human feedback."""
        try:
            await require_auth(websocket)
            feedback = data.get("feedback")
            if feedback:
                legacy_data = f"human_feedback {json.dumps({'feedback': feedback})}"
                await handle_human_feedback(websocket, legacy_data, self.manager)
        except WebSocketDisconnect:
            raise
    
    async def _handle_legacy_start(self, websocket: WebSocket, message: str) -> None:
        """Handle legacy 'start ' format (for backward compatibility)."""
        # Check if authenticated
        user_id = get_websocket_user_id(websocket)
        if not user_id:
            # Allow unauthenticated requests for backward compatibility
            # but log a warning
            logger.warning("Legacy start command without authentication")
        
        await handle_start_command(websocket, message, self.manager)
    
    async def _handle_legacy_chat(self, websocket: WebSocket, message: str) -> None:
        """Handle legacy chat format."""
        await handle_chat(websocket, message, self.manager)
    
    async def _handle_legacy_human_feedback(self, websocket: WebSocket, message: str) -> None:
        """Handle legacy human feedback format."""
        await handle_human_feedback(websocket, message, self.manager)
    
    async def _handle_resend_email_verification(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle resend email verification request."""
        try:
            email = data.get("email")
            if not email:
                await websocket.send_json({
                    "type": "resend_email_verification_response",
                    "success": False,
                    "error": "Email is required"
                })
                return
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                await websocket.send_json({
                    "type": "resend_email_verification_response",
                    "success": False,
                    "error": "Invalid email format"
                })
                return
            
            # Use UserManager to resend verification email
            logger.info(f"Attempting to resend verification email for: {email}")
            success = await self.user_manager.resend_email_verification(email)
            
            if success:
                await websocket.send_json({
                    "type": "resend_email_verification_response",
                    "success": True,
                    "message": "Verification email request processed. Please check your inbox (including spam folder). If you don't receive it, please check: 1) Email service is configured in Supabase dashboard, 2) User exists and is not already verified, 3) SMTP settings are properly configured."
                })
            else:
                await websocket.send_json({
                    "type": "resend_email_verification_response",
                    "success": False,
                    "error": "Failed to resend verification email. Please check: 1) Email service is configured in Supabase dashboard (Settings > Authentication > SMTP Settings), 2) User exists in Supabase, 3) Check server logs for detailed error information."
                })
            
        except Exception as e:
            logger.error(f"Error resending verification email: {e}", exc_info=True)
            await websocket.send_json({
                "type": "resend_email_verification_response",
                "success": False,
                "error": f"Failed to resend verification email: {str(e)}"
            })
    
    async def _handle_request_password_reset(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle password reset request (sends email with reset link)."""
        try:
            email = data.get("email")
            redirect_to = data.get("redirect_to")  # Optional: redirect URL after reset
            
            if not email:
                await websocket.send_json({
                    "type": "request_password_reset_response",
                    "success": False,
                    "error": "Email is required"
                })
                return
            
            # Use UserManager to request password reset
            success = await self.user_manager.request_password_reset(email, redirect_to)
            
            if success:
                await websocket.send_json({
                    "type": "request_password_reset_response",
                    "success": True,
                    "message": "Password reset email sent successfully. Please check your inbox for the reset link."
                })
            else:
                await websocket.send_json({
                    "type": "request_password_reset_response",
                    "success": False,
                    "error": "Failed to send password reset email. Please check if the email is valid and try again."
                })
            
        except Exception as e:
            logger.error(f"Error requesting password reset: {e}", exc_info=True)
            await websocket.send_json({
                "type": "request_password_reset_response",
                "success": False,
                "error": f"Failed to request password reset: {str(e)}"
            })
    
    async def _handle_reset_password(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle password reset with token from email link."""
        try:
            token = data.get("token")
            new_password = data.get("new_password")
            
            if not token:
                await websocket.send_json({
                    "type": "reset_password_response",
                    "success": False,
                    "error": "Token is required"
                })
                return
            
            if not new_password:
                await websocket.send_json({
                    "type": "reset_password_response",
                    "success": False,
                    "error": "New password is required"
                })
                return
            
            # Validate password strength (optional but recommended)
            if len(new_password) < 6:
                await websocket.send_json({
                    "type": "reset_password_response",
                    "success": False,
                    "error": "Password must be at least 6 characters long"
                })
                return
            
            # Use UserManager to reset password
            success = await self.user_manager.reset_password(token, new_password)
            
            if success:
                await websocket.send_json({
                    "type": "reset_password_response",
                    "success": True,
                    "message": "Password reset successfully. You can now sign in with your new password."
                })
            else:
                await websocket.send_json({
                    "type": "reset_password_response",
                    "success": False,
                    "error": "Failed to reset password. The token may be invalid or expired. Please request a new password reset."
                })
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}", exc_info=True)
            await websocket.send_json({
                "type": "reset_password_response",
                "success": False,
                "error": f"Failed to reset password: {str(e)}"
            })
    
    async def _handle_update_credits(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle update credits request (admin/management operation)."""
        try:
            # Require authentication
            await require_auth(websocket)
            user_id = get_websocket_user_id(websocket)
            if not user_id:
                await websocket.send_json({
                    "type": "error",
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required"
                })
                return
            
            # Get parameters
            target_user_id = data.get("user_id")  # Optional: if not provided, update current user
            amount = data.get("amount")
            operation = data.get("operation", "set")  # "set", "add", or "subtract"
            description = data.get("description", "Manual credit update")
            
            if amount is None:
                await websocket.send_json({
                    "type": "error",
                    "code": "MISSING_AMOUNT",
                    "message": "Amount is required"
                })
                return
            
            # Determine target user (default to current user)
            target_user_uuid = UUID(target_user_id) if target_user_id else UUID(user_id)
            
            # Get current balance
            current_balance = await self.credit_service.get_credit_balance(target_user_uuid)
            
            # Update credits based on operation
            if operation == "set":
                success = await self.credit_service.set_credits(
                    target_user_uuid,
                    amount,
                    description
                )
                if success:
                    credit_change = amount - current_balance
                    new_balance = amount
            elif operation == "add":
                success = await self.credit_service.add_credits(
                    target_user_uuid,
                    amount,
                    description
                )
                if success:
                    credit_change = amount
                    new_balance = current_balance + amount
            elif operation == "subtract":
                success = await self.credit_service.deduct_credits(
                    target_user_uuid,
                    amount,
                    description
                )
                if success:
                    credit_change = -min(amount, current_balance)
                    new_balance = max(0, current_balance - amount)
            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_OPERATION",
                    "message": "Operation must be 'set', 'add', or 'subtract'"
                })
                return
            
            if success:
                # Get updated balance
                updated_balance = await self.credit_service.get_credit_balance(target_user_uuid)
                
                await websocket.send_json({
                    "type": "update_credits_response",
                    "success": True,
                    "user_id": str(target_user_uuid),
                    "previous_balance": current_balance,
                    "new_balance": updated_balance,
                    "change": credit_change,
                    "operation": operation,
                    "message": f"Credits updated successfully"
                })
                logger.info(f"Credits updated for user {target_user_uuid}: {current_balance} -> {updated_balance} ({operation}: {amount})")
            else:
                await websocket.send_json({
                    "type": "update_credits_response",
                    "success": False,
                    "error": "Failed to update credits"
                })
                
        except ValueError as e:
            logger.error(f"Invalid UUID format: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INVALID_USER_ID",
                "message": "Invalid user ID format"
            })
        except Exception as e:
            logger.error(f"Error updating credits: {e}", exc_info=True)
            await websocket.send_json({
                "type": "update_credits_response",
                "success": False,
                "error": f"Failed to update credits: {str(e)}"
            })
    
    async def _handle_user_chat(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle user chat message (Gemini multimodal chatbot)."""
        try:
            # Check authentication
            user_id = get_websocket_user_id(websocket)
            if not user_id:
                await websocket.send_json({
                    "type": "error",
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication required"
                })
                return
            
            # Import chat_module services
            try:
                # Add both chat_module and chat_module/app to sys.path
                # This allows 'from app.xxx' imports to work inside chat_module files
                chat_module_path = Path(__file__).parent.parent.parent / "chat_module"
                chat_module_app_path = chat_module_path / "app"
                
                if str(chat_module_path) not in sys.path:
                    sys.path.insert(0, str(chat_module_path))
                if str(chat_module_app_path) not in sys.path:
                    sys.path.insert(0, str(chat_module_app_path))
                
                # Import using app directly (since app is now in sys.path)
                from services.supabase_service import SupabaseService
                from services.openai_service import OpenAIService
                from services.image_service import ImageService
                from services.web_scraper import WebScraperService
                from services.pdf_service import PDFService
            except ImportError as e:
                logger.error(f"Chat module services not available: {e}", exc_info=True)
                # Check if it's a dependency issue
                error_msg = str(e)
                if "pydantic_settings" in error_msg or "ModuleNotFoundError" in error_msg:
                    await websocket.send_json({
                        "type": "error",
                        "code": "CHAT_MODULE_UNAVAILABLE",
                        "message": "Chat module dependencies not installed. Please run: pip install -r chat_module/requirements.txt"
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "code": "CHAT_MODULE_UNAVAILABLE",
                        "message": f"Chat module is not available: {str(e)}"
                    })
                return
            
            # Initialize services
            supabase_service = SupabaseService()
            openai_service = OpenAIService()
            image_service = ImageService(supabase_service)
            web_scraper = WebScraperService()
            pdf_service = PDFService()
            
            # Extract message data
            message = data.get("message", "").strip()
            if not message:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": "Message is required"
                })
                return
            
            chat_id_str = data.get("chat_id")
            chat_id = UUID(chat_id_str) if chat_id_str else None
            images = data.get("images", [])
            pdf_urls = data.get("pdf_urls", [])
            enable_web_scraping = data.get("enable_web_scraping", True)
            
            user_uuid = UUID(user_id)
            
            # Get or create chat
            if not chat_id:
                # Create new chat
                chat_data = supabase_service.create_chat(user_uuid)
                chat_id = UUID(chat_data["id"])
            else:
                # Verify chat belongs to user
                chat = supabase_service.get_chat(chat_id, user_uuid)
                if not chat:
                    await websocket.send_json({
                        "type": "error",
                        "code": "CHAT_NOT_FOUND",
                        "message": "Chat not found or access denied"
                    })
                    return
            
            # Process images if provided
            image_urls = []
            if images:
                try:
                    # Upload images to Supabase Storage and get URLs
                    image_bytes_list = image_service.process_base64_images(images)
                    image_urls = await image_service.upload_multiple_images(image_bytes_list, user_id)
                except Exception as e:
                    logger.error(f"Error processing images: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "code": "IMAGE_ERROR",
                        "message": f"Failed to process images: {str(e)}"
                    })
                    return
            
            # Get chat history
            existing_messages = supabase_service.get_chat_messages(chat_id, user_uuid)
            
            # Prepare messages for LLM
            messages = []
            for msg in existing_messages:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "image_urls": msg.get("image_urls", [])
                })
            
            # Add user message
            messages.append({
                "role": "user",
                "content": message,
                "image_urls": image_urls
            })
            
            # Save user message
            supabase_service.create_message(
                chat_id=chat_id,
                role="user",
                content=message,
                image_urls=image_urls
            )
            
            # Determine if web scraping is needed
            web_context = ""
            web_sources = []
            metadata = {}
            
            if enable_web_scraping and openai_service.should_use_web_scraping(message):
                try:
                    web_context = await web_scraper.get_web_context(message, scrape_content=True)
                    if web_context:
                        # Extract sources from context
                        import re
                        source_pattern = r"Source:.*?\((https?://[^\)]+)\)"
                        web_sources = re.findall(source_pattern, web_context)
                        metadata["web_scraping_used"] = True
                        metadata["sources"] = web_sources
                except Exception as e:
                    logger.warning(f"Web scraping failed: {e}")
            
            # Extract text from PDFs if provided
            pdf_context = ""
            if pdf_urls:
                try:
                    pdf_context = await pdf_service.fetch_and_extract_text(pdf_urls)
                    if pdf_context:
                        metadata["pdfs_used"] = pdf_urls
                except Exception as e:
                    logger.error(f"Error processing PDFs: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "code": "PDF_ERROR",
                        "message": f"Failed to process PDFs: {str(e)}"
                    })
                    return
            
            # Generate response (Gemini or OpenAI)
            try:
                response_content = await openai_service.generate_response(
                    messages=messages,
                    images=None,  # Images are already in messages as image_urls
                    web_context=web_context if web_context else None,
                    pdf_context=pdf_context if pdf_context else None,
                )
            except Exception as e:
                logger.error(f"Error generating response: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "code": "GENERATION_ERROR",
                    "message": f"Failed to generate response: {str(e)}"
                })
                return
            
            # Save assistant message
            supabase_service.create_message(
                chat_id=chat_id,
                role="assistant",
                content=response_content,
                metadata=metadata
            )
            
            # Auto-generate heading if this is the first message
            if len(existing_messages) == 0:
                try:
                    heading = await openai_service.generate_heading(message)
                    supabase_service.update_chat_heading(chat_id, user_uuid, heading)
                except Exception as e:
                    logger.debug(f"Failed to generate heading: {e}")
            
            # Send response
            await websocket.send_json({
                "type": "user_chat",
                "chat_id": str(chat_id),
                "message": response_content,
                "image_urls": image_urls,
                "metadata": metadata
            })
            
        except ValueError as e:
            logger.error(f"Invalid UUID format: {e}")
            await websocket.send_json({
                "type": "error",
                "code": "INVALID_UUID",
                "message": f"Invalid UUID format: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Error handling user chat: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "code": "CHAT_ERROR",
                "message": f"Failed to process chat message: {str(e)}"
            })
    
    async def on_disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection."""
        remove_websocket_user(websocket)


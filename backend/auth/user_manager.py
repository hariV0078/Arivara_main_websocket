"""User profile management operations.

Simplified implementation using Supabase official patterns.
"""

from typing import Optional, Dict, Any
from supabase import Client
import logging
from .supabase_client import get_service_client

logger = logging.getLogger(__name__)


class UserManager:
    """
    Manage user profile operations using Supabase.
    
    Uses service role client to bypass RLS for admin operations.
    """
    
    def __init__(self, client: Optional[Client] = None):
        """
        Initialize UserManager.
        
        Args:
            client: Optional Supabase client (uses service client by default)
        """
        self.client = client or get_service_client()
    
    async def create_user_profile(
        self, 
        user_id: str, 
        email: str, 
        full_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new user profile in Supabase.
        
        Note: Supabase trigger should auto-create profile on user signup,
        but this method ensures it exists if trigger fails.
        
        Args:
            user_id: UUID from auth.users
            email: User email
            full_name: Optional full name
            
        Returns:
            Created user profile dictionary, or None if table doesn't exist
        """
        try:
            profile_data = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "credits": 100,  # Default starting credits
            }
            
            # Supabase insert pattern: table().insert().execute()
            result = self.client.table("user_profiles").insert(profile_data).execute()
            
            if result.data:
                logger.info(f"Created user profile for {user_id}")
                return result.data[0]
            else:
                logger.warning(f"No data returned when creating profile for {user_id}")
                return None
                
        except Exception as e:
            error_msg = str(e)
            # Supabase errors might be dict-like, try to extract message and code
            error_dict = {}
            if hasattr(e, '__dict__'):
                error_dict = e.__dict__
            elif isinstance(e, dict):
                error_dict = e
            
            # Check HTTP status code first - 409 is a conflict, not a FK error
            status_code = None
            if hasattr(e, 'status_code'):
                status_code = e.status_code
            elif 'status_code' in error_dict:
                status_code = error_dict.get('status_code')
            elif 'code' in error_dict and str(error_dict.get('code')).isdigit() and len(str(error_dict.get('code'))) == 3:
                status_code = int(error_dict.get('code'))
            
            # If it's a 409 Conflict, treat it as duplicate (not FK error)
            if status_code == 409:
                # This is a duplicate/conflict, not a FK error
                existing = await self.get_user_profile(user_id)
                if existing:
                    logger.info(f"User profile already exists for {user_id} (409 Conflict)")
                    return existing
                # If 409 but profile not found, it might be a race condition - try once more
                logger.debug(f"409 Conflict but profile not immediately available, retrying for {user_id}")
                try:
                    import asyncio
                    await asyncio.sleep(0.1)  # Brief delay for eventual consistency
                    existing = await self.get_user_profile(user_id)
                    if existing:
                        logger.info(f"User profile found on retry for {user_id}")
                        return existing
                except:
                    pass
                # Continue to check for other error types below
            
            # Check for foreign key constraint violation (wrong table reference)
            # Only trigger if it's actually a FK error (code 23503) AND mentions wrong table
            # AND it's NOT a 409 conflict
            error_code = str(error_dict.get("code", ""))
            is_fk_error = "23503" in error_code
            mentions_wrong_table = (
                "not present in table \"users\"" in error_msg or 
                "not present in table 'users'" in error_msg or
                ("violates foreign key constraint" in error_msg.lower() and "not present in table" in error_msg.lower())
            )
            
            # Only treat as FK error if BOTH conditions are met AND it's not a 409
            if is_fk_error and mentions_wrong_table and status_code != 409:
                logger.error(
                    f"Foreign key constraint error: user_profiles references wrong table. "
                    f"User {user_id} exists in auth.users but constraint points to public.users. "
                    f"Please run: python -m backend.database.fix_foreign_key"
                )
                # Try to get existing profile anyway (might have been created by trigger)
                existing = await self.get_user_profile(user_id)
                if existing:
                    logger.info(f"User profile found despite FK error for {user_id}")
                    return existing
                return None
            
            # Check if profile already exists (409 Conflict or duplicate key error)
            if "409" in error_msg or "conflict" in error_msg.lower() or "duplicate" in error_msg.lower() or "already exists" in error_msg.lower():
                existing = await self.get_user_profile(user_id)
                if existing:
                    logger.info(f"User profile already exists for {user_id}")
                    return existing
                # If 409 but profile not found, it might be a race condition - try once more
                logger.debug(f"409 Conflict but profile not immediately available, retrying for {user_id}")
                try:
                    import asyncio
                    await asyncio.sleep(0.1)  # Brief delay for eventual consistency
                    existing = await self.get_user_profile(user_id)
                    if existing:
                        logger.info(f"User profile found on retry for {user_id}")
                        return existing
                except:
                    pass
            
            # Check if profile exists before checking for table errors
            existing = await self.get_user_profile(user_id)
            if existing:
                logger.info(f"User profile already exists for {user_id}")
                return existing
            
            # Check if table doesn't exist (only if it's a real table error, not a conflict)
            if any(keyword in error_msg.lower() for keyword in ["pgrst205", "relation", "does not exist"]) and "409" not in error_msg and "conflict" not in error_msg.lower():
                logger.warning(
                    "Database table 'user_profiles' not found. "
                    "Please run: python -m backend.database.setup_schema"
                )
                return None
            
            logger.error(f"Error creating user profile: {e}")
            return None
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID from Supabase.
        
        Args:
            user_id: User UUID
            
        Returns:
            User profile dictionary or None if not found
        """
        try:
            # Supabase select pattern: table().select().eq().execute()
            result = self.client.table("user_profiles").select("*").eq("id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    async def update_user_profile(
        self, 
        user_id: str, 
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update user profile in Supabase.
        
        Args:
            user_id: User UUID
            data: Dictionary of fields to update (updated_at is auto-handled by trigger)
            
        Returns:
            Updated user profile dictionary or None
        """
        try:
            # Supabase update pattern: table().update().eq().execute()
            # Note: updated_at is handled by database trigger
            result = self.client.table("user_profiles").update(data).eq("id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                logger.info(f"Updated user profile for {user_id}")
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return None
    
    async def get_user_credits(self, user_id: str) -> int:
        """
        Get user's current credit balance.
        
        Args:
            user_id: User UUID
            
        Returns:
            Credit balance (defaults to 0 if user not found)
        """
        profile = await self.get_user_profile(user_id)
        if profile:
            return profile.get("credits", 0)
        return 0
    
    async def ensure_user_profile(
        self, 
        user_id: str, 
        email: str, 
        full_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ensure user profile exists, create if it doesn't.
        
        Args:
            user_id: User UUID
            email: User email
            full_name: Optional full name
            
        Returns:
            User profile dictionary
        """
        profile = await self.get_user_profile(user_id)
        if not profile:
            profile = await self.create_user_profile(user_id, email, full_name)
        return profile
    
    async def resend_email_verification(self, email: str) -> bool:
        """
        Resend email verification for a user.
        
        Uses Supabase Auth API to resend the verification email.
        First checks if the user exists and their verification status.
        
        Args:
            email: User email address
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            import httpx
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                logger.error("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
                return False
            
            # First, check if user exists and their verification status (using service role key if available)
            user_exists = False
            user_verified = False
            
            if service_role_key:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        # Get user by email using admin API
                        admin_response = await http_client.get(
                            f"{supabase_url}/auth/v1/admin/users",
                            headers={
                                "apikey": service_role_key,
                                "Authorization": f"Bearer {service_role_key}",
                                "Content-Type": "application/json"
                            },
                            params={"email": email}
                        )
                        
                        if admin_response.status_code == 200:
                            users_data = admin_response.json()
                            if isinstance(users_data, dict) and "users" in users_data:
                                users = users_data["users"]
                                if users and len(users) > 0:
                                    user_exists = True
                                    user = users[0]
                                    # Check if email is verified
                                    user_verified = user.get("email_confirmed_at") is not None
                                    logger.info(f"User found: exists={user_exists}, verified={user_verified}")
                except Exception as e:
                    logger.warning(f"Could not check user status: {e}")
            
            # If user is already verified, inform them
            if user_exists and user_verified:
                logger.info(f"User {email} is already verified")
                # Still return True as this is not an error, just informational
            
            # Use service role key if available (more reliable for admin operations)
            key_to_use = service_role_key if service_role_key else supabase_key
            key_type = "service_role" if service_role_key else "anon"
            
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                resend_response = await http_client.post(
                    f"{supabase_url}/auth/v1/resend",
                    headers={
                        "apikey": key_to_use,
                        "Content-Type": "application/json"
                    },
                    json={
                        "type": "signup",
                        "email": email
                    }
                )
                
                logger.info(f"Resend API response status: {resend_response.status_code} (using {key_type} key)")
                logger.info(f"Resend API response body: {resend_response.text}")
                
                # Supabase returns 200 even if email doesn't exist (security best practice)
                if resend_response.status_code == 200:
                    response_data = {}
                    try:
                        if resend_response.text:
                            response_data = resend_response.json()
                    except Exception:
                        pass
                    
                    # Check if there's an error message in the response
                    if isinstance(response_data, dict):
                        if "error" in response_data:
                            error_msg = str(response_data.get("error", ""))
                            logger.error(f"Error in response: {error_msg}")
                            return False
                        elif "message" in response_data:
                            # Some responses include a message
                            message = str(response_data.get("message", ""))
                            logger.info(f"Response message: {message}")
                    
                    # Empty response {} usually means Supabase accepted but email might not be sent
                    # This can happen if:
                    # 1. Email service is not configured
                    # 2. User doesn't exist (Supabase doesn't reveal this for security)
                    # 3. User is already verified
                    if not response_data:
                        logger.warning(
                            f"Empty response from Supabase. This usually means:\n"
                            f"1. Email service may not be configured in Supabase dashboard\n"
                            f"2. User may not exist (Supabase doesn't reveal this)\n"
                            f"3. User may already be verified\n"
                            f"Please check Supabase email configuration and user status."
                        )
                    
                    logger.info(f"Verification email request processed for: {email}")
                    return True
                else:
                    error_text = resend_response.text
                    logger.error(f"Failed to resend verification email. Status: {resend_response.status_code}, Error: {error_text}")
                    return False
                
        except Exception as e:
            logger.error(f"Error resending verification email: {e}", exc_info=True)
            return False
    
    async def request_password_reset(self, email: str, redirect_to: Optional[str] = None) -> bool:
        """
        Request a password reset email for a user.
        
        Uses Supabase Auth API to send a password reset email with a link.
        The link will be automatically generated by Supabase and will redirect
        to the URL configured in Supabase dashboard (or the redirect_to parameter).
        
        Args:
            email: User email address
            redirect_to: Optional redirect URL after password reset (must be whitelisted in Supabase)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            import httpx
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                logger.error("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
                return False
            
            payload = {
                "email": email
            }
            
            # Add redirect_to if provided (must be whitelisted in Supabase settings)
            if redirect_to:
                payload["redirect_to"] = redirect_to
            
            async with httpx.AsyncClient() as http_client:
                reset_response = await http_client.post(
                    f"{supabase_url}/auth/v1/recover",
                    headers={
                        "apikey": supabase_key,
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                # Supabase returns 200 even if email doesn't exist (security best practice)
                if reset_response.status_code == 200:
                    logger.info(f"Password reset email sent successfully for: {email}")
                    return True
                else:
                    error_text = reset_response.text
                    logger.error(f"Failed to send password reset email: {error_text}")
                    return False
                
        except Exception as e:
            logger.error(f"Error requesting password reset: {e}", exc_info=True)
            return False
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using a token from the password reset email.
        
        This verifies the token and sets the new password.
        The token should be extracted from the email link URL.
        
        Args:
            token: Password reset token from the email link (hash fragment)
            new_password: New password to set
            
        Returns:
            True if password was reset successfully, False otherwise
        """
        try:
            import httpx
            import os
            
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                logger.error("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
                return False
            
            async with httpx.AsyncClient() as http_client:
                # Update password using the recovery token
                # The token from the email link is used as Bearer token
                update_response = await http_client.put(
                    f"{supabase_url}/auth/v1/user",
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "password": new_password
                    }
                )
                
                if update_response.status_code in [200, 201]:
                    logger.info("Password reset successfully")
                    return True
                else:
                    error_text = update_response.text
                    logger.error(f"Failed to reset password: {error_text}")
                    return False
                
        except Exception as e:
            logger.error(f"Error resetting password: {e}", exc_info=True)
            return False


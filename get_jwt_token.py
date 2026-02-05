"""
Simple script to get JWT access token for a user.

Usage:
    python get_jwt_token.py

Or with arguments:
    python get_jwt_token.py --email user@example.com --password password123
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client
except ImportError:
    print("❌ Error: supabase package not installed")
    print("Install it with: pip install supabase")
    sys.exit(1)


def get_token(email: str, password: str, create_new: bool = False):
    """
    Get JWT access token for a user.
    
    Args:
        email: User email
        password: User password
        create_new: If True, create new user. If False, sign in existing user.
    
    Returns:
        JWT access token string or None
    """
    # Get Supabase configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env file")
        print("\nAdd these to your .env file:")
        print("SUPABASE_URL=https://your-project.supabase.co")
        print("SUPABASE_ANON_KEY=your-anon-key-here")
        return None
    
    # Create Supabase client
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"❌ Error creating Supabase client: {e}")
        return None
    
    # Try to create user or sign in
    try:
        if create_new:
            print(f"📝 Creating new user: {email}")
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                print("✅ User created successfully")
                if response.session:
                    token = response.session.access_token
                    print(f"✅ Access token received")
                    return token
                else:
                    print("⚠️  No session. User may need email confirmation.")
                    print("🔄 Attempting to sign in...")
                    # Fall through to sign in
        else:
            print(f"🔐 Signing in user: {email}")
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.session:
                token = response.session.access_token
                print("✅ Signed in successfully")
                return token
            else:
                print("❌ No session returned")
                return None
                
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        
        # If user already exists, try to sign in
        if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
            if not create_new:
                print("🔄 User exists. Attempting to sign in...")
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    if response.session:
                        token = response.session.access_token
                        print("✅ Signed in successfully")
                        return token
                except Exception as e2:
                    print(f"❌ Sign in failed: {e2}")
        
        return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Get JWT access token for a user")
    parser.add_argument("--email", type=str, help="User email address")
    parser.add_argument("--password", type=str, help="User password")
    parser.add_argument("--create", action="store_true", help="Create new user instead of signing in")
    
    args = parser.parse_args()
    
    # Get email and password
    email = args.email
    password = args.password
    
    if not email:
        email = input("Enter email: ").strip()
    
    if not password:
        import getpass
        password = getpass.getpass("Enter password: ").strip()
    
    if not email or not password:
        print("❌ Error: Email and password are required")
        sys.exit(1)
    
    print("=" * 60)
    print("Getting JWT Access Token")
    print("=" * 60)
    print()
    
    # Get token
    token = get_token(email, password, create_new=args.create)
    
    if token:
        print()
        print("=" * 60)
        print("✅ SUCCESS - JWT Access Token:")
        print("=" * 60)
        print(token)
        print()
        print("=" * 60)
        print("📋 Use this token in WebSocket:")
        print("=" * 60)
        print(f'{{"type": "authenticate", "token": "{token}"}}')
        print()
        print("=" * 60)
        print("📋 Or in HTTP requests:")
        print("=" * 60)
        print(f'Authorization: Bearer {token}')
        print()
        
        # Optionally save to file
        save = input("💾 Save token to file? (y/n): ").strip().lower()
        if save == 'y':
            token_file = ".token"
            with open(token_file, 'w') as f:
                f.write(token)
            print(f"✅ Token saved to {token_file}")
            print("⚠️  WARNING: Keep this file secure and don't commit it to git!")
    else:
        print()
        print("❌ Failed to get access token")
        sys.exit(1)


if __name__ == "__main__":
    main()


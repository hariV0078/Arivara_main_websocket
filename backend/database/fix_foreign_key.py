"""
Fix foreign key constraint for user_profiles table.

This script fixes the foreign key constraint that incorrectly references
public.users instead of auth.users.

Usage:
    python backend/database/fix_foreign_key.py
    OR
    python -m backend.database.fix_foreign_key
"""

import os
import sys
from pathlib import Path

# Add project root to path before loading dotenv
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

# Database connection parameters
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")


def get_db_connection():
    """Connect to Supabase database."""
    if not all([USER, PASSWORD, HOST, PORT, DBNAME]):
        print("[ERROR] Missing required environment variables")
        print("\nMake sure these environment variables are set:")
        print("  - user (database user)")
        print("  - password (database password)")
        print("  - host (database host)")
        print("  - port (database port, usually 5432)")
        print("  - dbname (database name)")
        return None
    
    # Try multiple connection methods
    connection_strings = [
        # Direct connection
        f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}",
        # With IPv4 preference
        f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?connect_timeout=10",
    ]
    
    for conn_str in connection_strings:
        try:
            print(f"[INFO] Attempting connection to {HOST}...")
            connection = psycopg2.connect(conn_str)
            connection.autocommit = True
            print("[OK] Connected to database")
            return connection
        except psycopg2.OperationalError as e:
            if "Network is unreachable" in str(e) or "IPv6" in str(e):
                # Try with IPv4 only
                try:
                    import socket
                    # Resolve hostname to IPv4
                    host_ip = socket.gethostbyname(HOST)
                    print(f"[INFO] Resolved {HOST} to IPv4: {host_ip}")
                    connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=host_ip,
                        port=PORT,
                        dbname=DBNAME,
                        connect_timeout=10
                    )
                    connection.autocommit = True
                    print("[OK] Connected to database using IPv4")
                    return connection
                except Exception as e2:
                    print(f"[WARNING] IPv4 connection also failed: {e2}")
                    continue
            else:
                print(f"[WARNING] Connection attempt failed: {e}")
                continue
        except Exception as e:
            print(f"[WARNING] Connection attempt failed: {e}")
            continue
    
    print(f"[ERROR] All connection attempts failed")
    print("\nTroubleshooting:")
    print("1. Check if your IP is whitelisted in Supabase Dashboard -> Settings -> Database")
    print("2. Try using the connection pooler port (usually 6543) instead of direct port (5432)")
    print("3. Check if you're behind a firewall/VPN that blocks database connections")
    print("4. Verify your database credentials in Supabase Dashboard")
    return None


def fix_foreign_key_constraint(conn):
    """Fix the foreign key constraint on user_profiles table."""
    try:
        cursor = conn.cursor()
        
        # Check if the constraint exists and what it references
        cursor.execute("""
            SELECT 
                conname as constraint_name,
                pg_get_constraintdef(oid) as constraint_definition
            FROM pg_constraint
            WHERE conrelid = 'public.user_profiles'::regclass
            AND contype = 'f'
            AND conname LIKE '%id%fkey%';
        """)
        
        constraints = cursor.fetchall()
        
        print("\n[INFO] Checking existing foreign key constraints on user_profiles...")
        
        # Drop the incorrect constraint if it exists
        # The constraint might be named user_profiles_id_fkey or similar
        cursor.execute("""
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'public.user_profiles'::regclass 
            AND contype = 'f'
            AND conname LIKE '%id%fkey%';
        """)
        
        existing_constraints = cursor.fetchall()
        
        for (constraint_name,) in existing_constraints:
            print(f"[INFO] Found constraint: {constraint_name}")
            
            # Get the constraint definition to check what it references
            cursor.execute("""
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = %s;
            """, (constraint_name,))
            
            definition = cursor.fetchone()[0]
            print(f"[INFO] Constraint definition: {definition}")
            
            # If it references the wrong table (public.users instead of auth.users), drop it
            if 'users' in definition and 'auth.users' not in definition:
                print(f"[INFO] Dropping incorrect constraint: {constraint_name}")
                cursor.execute(f'ALTER TABLE public.user_profiles DROP CONSTRAINT IF EXISTS "{constraint_name}";')
                print(f"[OK] Dropped constraint: {constraint_name}")
        
        # Now create the correct constraint pointing to auth.users
        print("\n[INFO] Creating correct foreign key constraint...")
        cursor.execute("""
            ALTER TABLE public.user_profiles 
            DROP CONSTRAINT IF EXISTS user_profiles_id_fkey;
        """)
        
        cursor.execute("""
            ALTER TABLE public.user_profiles 
            ADD CONSTRAINT user_profiles_id_fkey 
            FOREIGN KEY (id) 
            REFERENCES auth.users(id) 
            ON DELETE CASCADE;
        """)
        
        print("[OK] Created correct foreign key constraint: user_profiles_id_fkey -> auth.users(id)")
        
        # Verify the constraint
        cursor.execute("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'user_profiles_id_fkey';
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"[OK] Verified constraint: {result[0]}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Error fixing foreign key constraint: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    print("=" * 60)
    print("Fixing Foreign Key Constraint for user_profiles")
    print("=" * 60)
    print()
    
    conn = get_db_connection()
    if not conn:
        sys.exit(1)
    
    try:
        success = fix_foreign_key_constraint(conn)
        
        if success:
            print("\n" + "=" * 60)
            print("[SUCCESS] Foreign key constraint fixed successfully!")
            print("=" * 60)
            print("\nThe user_profiles table now correctly references auth.users(id)")
        else:
            print("\n" + "=" * 60)
            print("[ERROR] Failed to fix foreign key constraint")
            print("=" * 60)
            sys.exit(1)
            
    finally:
        conn.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()


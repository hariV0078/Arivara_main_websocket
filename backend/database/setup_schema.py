"""
Supabase schema setup using Python.

This script can set up the database schema in two modes:
1. Incremental (default): Creates tables/indexes/policies if they don't exist
2. From scratch: Drops all existing objects and recreates everything

Usage:
    # Incremental setup (safe, won't delete existing data)
    python backend/database/setup_schema.py
    
    # From scratch setup (WARNING: Deletes all data!)
    python backend/database/setup_schema.py --from-scratch
    
    OR
    python -m backend.database.setup_schema [--from-scratch]

Alternative:
    You can also run the SQL file directly in Supabase Dashboard:
    backend/database/setup_schema.sql
"""

import os
import sys
import argparse
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
    try:
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        connection.autocommit = True
        print("[OK] Connected to database")
        return connection
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return None


def drop_all_objects(conn):
    """Drop all existing objects for fresh setup."""
    try:
        cursor = conn.cursor()
        
        print("\n[WARNING] Dropping all existing objects...")
        
        # Drop triggers
        cursor.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
        cursor.execute("DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;")
        print("[OK] Dropped triggers")
        
        # Drop functions
        cursor.execute("DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;")
        cursor.execute("DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;")
        print("[OK] Dropped functions")
        
        # Drop tables (in reverse dependency order)
        cursor.execute("DROP TABLE IF EXISTS public.research_documents CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS public.research_history CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS public.credit_transactions CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS public.user_profiles CASCADE;")
        print("[OK] Dropped tables")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error dropping objects: {e}")
        return False


def create_tables(conn, from_scratch=False):
    """Create all required tables."""
    try:
        cursor = conn.cursor()
        
        if from_scratch:
            create_stmt = "CREATE TABLE"
        else:
            create_stmt = "CREATE TABLE IF NOT EXISTS"
        
        cursor.execute(f"""
            {create_stmt} public.user_profiles (
                id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                full_name TEXT,
                credits INTEGER DEFAULT 100 NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            );
        """)
        print("[OK] Created user_profiles table")
        
        cursor.execute(f"""
            {create_stmt} public.credit_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
                amount INTEGER NOT NULL,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
                description TEXT,
                balance_after INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            );
        """)
        print("[OK] Created credit_transactions table")
        
        cursor.execute(f"""
            {create_stmt} public.research_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
                query TEXT NOT NULL,
                report_type TEXT NOT NULL,
                credits_used INTEGER NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
                result_summary TEXT,
                token_usage JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                completed_at TIMESTAMPTZ
            );
        """)
        print("[OK] Created research_history table")
        
        cursor.execute(f"""
            {create_stmt} public.research_documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                research_id UUID NOT NULL REFERENCES public.research_history(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'markdown')),
                file_size INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            );
        """)
        print("[OK] Created research_documents table")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")
        return False


def add_missing_columns(conn):
    """Add missing columns to existing tables (for incremental updates)."""
    try:
        cursor = conn.cursor()
        
        # Check if token_usage column exists in research_history
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'research_history' 
            AND column_name = 'token_usage';
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE public.research_history 
                ADD COLUMN token_usage JSONB;
            """)
            print("[OK] Added token_usage column to research_history table")
        else:
            print("[SKIP] token_usage column already exists in research_history")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error adding missing columns: {e}")
        return False


def create_indexes(conn, from_scratch=False):
    """Create indexes for better query performance."""
    try:
        cursor = conn.cursor()
        
        indexes = [
            ("idx_credit_transactions_user_id", "credit_transactions", "user_id"),
            ("idx_credit_transactions_created_at", "credit_transactions", "created_at DESC"),
            ("idx_research_history_user_id", "research_history", "user_id"),
            ("idx_research_history_created_at", "research_history", "created_at DESC"),
            ("idx_research_history_status", "research_history", "status"),
            ("idx_research_documents_research_id", "research_documents", "research_id"),
        ]
        
        for index_name, table_name, column in indexes:
            if from_scratch:
                cursor.execute(f"CREATE INDEX {index_name} ON public.{table_name}({column});")
            else:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON public.{table_name}({column});")
            print(f"[OK] Created index {index_name}")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error creating indexes: {e}")
        return False


def enable_rls(conn):
    """Enable Row Level Security on all tables."""
    try:
        cursor = conn.cursor()
        tables = ["user_profiles", "credit_transactions", "research_history", "research_documents"]
        
        for table in tables:
            cursor.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
            print(f"[OK] Enabled RLS on {table}")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error enabling RLS: {e}")
        return False


def create_rls_policies(conn):
    """Create Row Level Security policies."""
    try:
        cursor = conn.cursor()
        
        # Drop existing policies
        policies = [
            ("Users can view own profile", "user_profiles"),
            ("Users can update own profile", "user_profiles"),
            ("Users can view own transactions", "credit_transactions"),
            ("Users can view own research", "research_history"),
            ("Users can insert own research", "research_history"),
            ("Users can update own research", "research_history"),
            ("Users can view own documents", "research_documents"),
            ("Users can insert own documents", "research_documents"),
        ]
        
        for policy_name, table in policies:
            cursor.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON public.{table};')
        
        # Create policies
        cursor.execute('CREATE POLICY "Users can view own profile" ON public.user_profiles FOR SELECT USING (auth.uid() = id);')
        cursor.execute('CREATE POLICY "Users can update own profile" ON public.user_profiles FOR UPDATE USING (auth.uid() = id);')
        cursor.execute('CREATE POLICY "Users can view own transactions" ON public.credit_transactions FOR SELECT USING (auth.uid() = user_id);')
        cursor.execute('CREATE POLICY "Users can view own research" ON public.research_history FOR SELECT USING (auth.uid() = user_id);')
        cursor.execute('CREATE POLICY "Users can insert own research" ON public.research_history FOR INSERT WITH CHECK (auth.uid() = user_id);')
        cursor.execute('CREATE POLICY "Users can update own research" ON public.research_history FOR UPDATE USING (auth.uid() = user_id);')
        cursor.execute('CREATE POLICY "Users can view own documents" ON public.research_documents FOR SELECT USING (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));')
        cursor.execute('CREATE POLICY "Users can insert own documents" ON public.research_documents FOR INSERT WITH CHECK (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));')
        
        print("[OK] Created RLS policies")
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error creating RLS policies: {e}")
        return False


def create_functions_and_triggers(conn):
    """Create database functions and triggers."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE OR REPLACE FUNCTION public.handle_new_user()
            RETURNS TRIGGER AS $$
            BEGIN
                INSERT INTO public.user_profiles (id, email, full_name, credits)
                VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'full_name', NULL), 100);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql SECURITY DEFINER;
        """)
        
        cursor.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
        cursor.execute("CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();")
        
        cursor.execute("""
            CREATE OR REPLACE FUNCTION public.update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        cursor.execute("DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;")
        cursor.execute("CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON public.user_profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();")
        
        print("[OK] Created functions and triggers")
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error creating functions and triggers: {e}")
        return False


def setup_schema(from_scratch=False):
    """
    Main function to set up the complete schema.
    
    Args:
        from_scratch: If True, drops all existing objects before creating new ones
    """
    if from_scratch:
        print("=" * 70)
        print("WARNING: FROM-SCRATCH MODE")
        print("=" * 70)
        print("This will DELETE ALL existing data and recreate the schema!")
        print("=" * 70)
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return False
        print("\nStarting Supabase schema setup from scratch...\n")
    else:
        print("Starting Supabase schema setup (incremental mode)...\n")
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        success = True
        
        if from_scratch:
            success &= drop_all_objects(conn)
            print()
        
        success &= create_tables(conn, from_scratch=from_scratch)
        
        if not from_scratch:
            # Add any missing columns in incremental mode
            success &= add_missing_columns(conn)
        
        success &= create_indexes(conn, from_scratch=from_scratch)
        success &= enable_rls(conn)
        success &= create_rls_policies(conn)
        success &= create_functions_and_triggers(conn)
        
        if success:
            print("\n" + "=" * 70)
            print("[SUCCESS] Schema setup completed successfully!")
            print("=" * 70)
            print("\nNext steps:")
            print("1. Create a storage bucket named 'research-documents' in Supabase Storage")
            print("2. Set up storage policies for the bucket if needed")
            print("3. Test user registration to verify the trigger works")
        else:
            print("\n[ERROR] Schema setup completed with errors")
        
        return success
    finally:
        conn.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up Supabase database schema")
    parser.add_argument(
        "--from-scratch",
        action="store_true",
        help="Drop all existing objects and recreate from scratch (WARNING: Deletes all data!)"
    )
    args = parser.parse_args()
    
    success = setup_schema(from_scratch=args.from_scratch)
    sys.exit(0 if success else 1)


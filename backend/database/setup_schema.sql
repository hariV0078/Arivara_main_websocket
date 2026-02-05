-- ============================================================================
-- Supabase Database Setup Script - Complete From Scratch
-- ============================================================================
-- This script sets up the complete database schema for the Arivara Research Agent
-- Run this in Supabase Dashboard -> SQL Editor
-- 
-- Prerequisites:
-- 1. Supabase project must have auth enabled
-- 2. You must have database admin access
-- ============================================================================

-- ============================================================================
-- STEP 1: Drop existing objects (for fresh setup)
-- ============================================================================

-- Drop triggers first (using DO block to handle errors gracefully)
DO $$
BEGIN
    -- Drop trigger on auth.users (this should always work)
    DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    
    -- Drop trigger on user_profiles only if table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_profiles') THEN
        DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Ignore errors during cleanup
        NULL;
END $$;

-- Drop functions
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

-- Drop tables (in reverse dependency order)
DROP TABLE IF EXISTS public.messages CASCADE;
DROP TABLE IF EXISTS public.chats CASCADE;
DROP TABLE IF EXISTS public.research_documents CASCADE;
DROP TABLE IF EXISTS public.research_history CASCADE;
DROP TABLE IF EXISTS public.credit_transactions CASCADE;
DROP TABLE IF EXISTS public.user_profiles CASCADE;

-- ============================================================================
-- STEP 2: Create tables
-- ============================================================================

-- User profiles table
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    credits INTEGER DEFAULT 100 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Credit transactions table
CREATE TABLE public.credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
    description TEXT,
    balance_after INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Research history table
CREATE TABLE public.research_history (
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

-- Research documents table
CREATE TABLE public.research_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id UUID NOT NULL REFERENCES public.research_history(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'markdown')),
    file_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Chat module tables (user-memory chatbot)
-- Chats table
CREATE TABLE public.chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    heading TEXT,
    auto_heading TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Messages table
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    image_urls TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ============================================================================
-- STEP 3: Create indexes for performance
-- ============================================================================

-- Indexes for credit_transactions
CREATE INDEX idx_credit_transactions_user_id ON public.credit_transactions(user_id);
CREATE INDEX idx_credit_transactions_created_at ON public.credit_transactions(created_at DESC);

-- Indexes for research_history
CREATE INDEX idx_research_history_user_id ON public.research_history(user_id);
CREATE INDEX idx_research_history_created_at ON public.research_history(created_at DESC);
CREATE INDEX idx_research_history_status ON public.research_history(status);

-- Indexes for research_documents
CREATE INDEX idx_research_documents_research_id ON public.research_documents(research_id);

-- Indexes for chats
CREATE INDEX idx_chats_user_id ON public.chats(user_id);
CREATE INDEX idx_chats_updated_at ON public.chats(updated_at DESC);

-- Indexes for messages
CREATE INDEX idx_messages_chat_id ON public.messages(chat_id);
CREATE INDEX idx_messages_created_at ON public.messages(created_at);

-- ============================================================================
-- STEP 4: Enable Row Level Security (RLS)
-- ============================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- STEP 5: Create RLS policies
-- ============================================================================

-- Drop existing policies (if any) - wrapped in DO block for safety
DO $$
BEGIN
    -- User profiles policies
    DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
    DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
    
    -- Credit transactions policies
    DROP POLICY IF EXISTS "Users can view own transactions" ON public.credit_transactions;
    
    -- Research history policies
    DROP POLICY IF EXISTS "Users can view own research" ON public.research_history;
    DROP POLICY IF EXISTS "Users can insert own research" ON public.research_history;
    DROP POLICY IF EXISTS "Users can update own research" ON public.research_history;
    
    -- Research documents policies
    DROP POLICY IF EXISTS "Users can view own documents" ON public.research_documents;
    DROP POLICY IF EXISTS "Users can insert own documents" ON public.research_documents;
EXCEPTION
    WHEN OTHERS THEN
        -- Ignore errors - policies might not exist or tables might not exist
        NULL;
END $$;

-- Create policies
CREATE POLICY "Users can view own profile" 
    ON public.user_profiles 
    FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON public.user_profiles 
    FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY "Users can view own transactions" 
    ON public.credit_transactions 
    FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own research" 
    ON public.research_history 
    FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own research" 
    ON public.research_history 
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own research" 
    ON public.research_history 
    FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own documents" 
    ON public.research_documents 
    FOR SELECT 
    USING (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));

CREATE POLICY "Users can insert own documents" 
    ON public.research_documents 
    FOR INSERT 
    WITH CHECK (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));

-- RLS Policies for chats table
CREATE POLICY "Users can view their own chats"
    ON public.chats FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own chats"
    ON public.chats FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own chats"
    ON public.chats FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own chats"
    ON public.chats FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for messages table
CREATE POLICY "Users can view messages from their own chats"
    ON public.messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages to their own chats"
    ON public.messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update messages in their own chats"
    ON public.messages FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages from their own chats"
    ON public.messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

-- ============================================================================
-- STEP 6: Create functions
-- ============================================================================

-- Function to automatically create user profile when a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name, credits)
    VALUES (
        NEW.id, 
        NEW.email, 
        COALESCE(NEW.raw_user_meta_data->>'full_name', NULL), 
        100
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 7: Create triggers
-- ============================================================================

-- Trigger to create user profile on new user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Trigger to update updated_at on user profile updates
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger to update updated_at on chats updates
CREATE TRIGGER update_chats_updated_at
    BEFORE UPDATE ON public.chats
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- STEP 8: Grant permissions (if needed)
-- ============================================================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
GRANT SELECT ON public.credit_transactions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.research_history TO authenticated;
GRANT SELECT, INSERT ON public.research_documents TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.chats TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.messages TO authenticated;

-- ============================================================================
-- Setup Complete!
-- ============================================================================
-- The database schema has been set up successfully.
-- 
-- Next steps:
-- 1. Create a storage bucket named 'research-documents' in Supabase Storage
-- 2. Create a storage bucket named 'chatbot-images' in Supabase Storage (for chat module)
-- 3. Set up storage policies for the buckets if needed
-- 4. Test user registration to verify the trigger works
-- ============================================================================

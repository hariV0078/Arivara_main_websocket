-- ============================================================================
-- Supabase Database Setup Script - Simple Version
-- ============================================================================
-- This is a simplified version that's more robust for Supabase SQL Editor
-- Run this in Supabase Dashboard -> SQL Editor
-- ============================================================================

-- Step 1: Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS public.research_documents CASCADE;
DROP TABLE IF EXISTS public.research_history CASCADE;
DROP TABLE IF EXISTS public.credit_transactions CASCADE;
DROP TABLE IF EXISTS public.user_profiles CASCADE;

-- Step 2: Drop functions if they exist
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

-- Step 3: Drop triggers if they exist
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Step 4: Create user_profiles table
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    credits INTEGER DEFAULT 100 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Step 5: Create credit_transactions table
CREATE TABLE public.credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
    description TEXT,
    balance_after INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Step 6: Create research_history table
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

-- Step 7: Create research_documents table
CREATE TABLE public.research_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id UUID NOT NULL REFERENCES public.research_history(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'markdown')),
    file_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Step 8: Create indexes
CREATE INDEX idx_credit_transactions_user_id ON public.credit_transactions(user_id);
CREATE INDEX idx_credit_transactions_created_at ON public.credit_transactions(created_at DESC);
CREATE INDEX idx_research_history_user_id ON public.research_history(user_id);
CREATE INDEX idx_research_history_created_at ON public.research_history(created_at DESC);
CREATE INDEX idx_research_history_status ON public.research_history(status);
CREATE INDEX idx_research_documents_research_id ON public.research_documents(research_id);

-- Step 9: Enable Row Level Security
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_documents ENABLE ROW LEVEL SECURITY;

-- Step 10: Create RLS policies
CREATE POLICY "Users can view own profile" 
    ON public.user_profiles FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON public.user_profiles FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY "Users can view own transactions" 
    ON public.credit_transactions FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own research" 
    ON public.research_history FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own research" 
    ON public.research_history FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own research" 
    ON public.research_history FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own documents" 
    ON public.research_documents FOR SELECT 
    USING (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));

CREATE POLICY "Users can insert own documents" 
    ON public.research_documents FOR INSERT 
    WITH CHECK (auth.uid() = (SELECT user_id FROM public.research_history WHERE id = research_id));

-- Step 11: Create functions
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

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 12: Create triggers
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Step 13: Grant permissions
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;
GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
GRANT SELECT ON public.credit_transactions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.research_history TO authenticated;
GRANT SELECT, INSERT ON public.research_documents TO authenticated;

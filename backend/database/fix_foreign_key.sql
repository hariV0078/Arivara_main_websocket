-- Fix Foreign Key Constraint for user_profiles table
-- 
-- Run this SQL in Supabase Dashboard -> SQL Editor
-- This fixes the foreign key constraint that incorrectly references
-- public.users instead of auth.users

-- Step 1: Show all current foreign key constraints on user_profiles
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'public.user_profiles'::regclass
AND contype = 'f'
ORDER BY conname;

-- Step 2: Drop ALL foreign key constraints on user_profiles.id
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    -- Find and drop ALL foreign key constraints on user_profiles table
    FOR constraint_name IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.user_profiles'::regclass
        AND contype = 'f'
    LOOP
        BEGIN
            EXECUTE format('ALTER TABLE public.user_profiles DROP CONSTRAINT %I', constraint_name);
            RAISE NOTICE 'Dropped constraint: %', constraint_name;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Could not drop constraint %: %', constraint_name, SQLERRM;
        END;
    END LOOP;
END $$;

-- Step 3: Verify all constraints are dropped
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'public.user_profiles'::regclass
AND contype = 'f';

-- Step 4: Create the correct foreign key constraint pointing to auth.users
ALTER TABLE public.user_profiles 
ADD CONSTRAINT user_profiles_id_fkey 
FOREIGN KEY (id) 
REFERENCES auth.users(id) 
ON DELETE CASCADE;

-- Step 5: Verify the new constraint
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conname = 'user_profiles_id_fkey';

-- Expected output should show:
-- constraint_name: user_profiles_id_fkey
-- constraint_definition: FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE


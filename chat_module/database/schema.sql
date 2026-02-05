-- Chatbot Plugin Database Schema for Supabase

-- Create chats table
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    heading TEXT,
    auto_heading TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    image_urls TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Enable Row Level Security (RLS)
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chats table
-- Users can only see their own chats
CREATE POLICY "Users can view their own chats"
    ON chats FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own chats
CREATE POLICY "Users can insert their own chats"
    ON chats FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own chats
CREATE POLICY "Users can update their own chats"
    ON chats FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own chats
CREATE POLICY "Users can delete their own chats"
    ON chats FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for messages table
-- Users can only see messages from their own chats
CREATE POLICY "Users can view messages from their own chats"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

-- Users can insert messages to their own chats
CREATE POLICY "Users can insert messages to their own chats"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

-- Users can update messages in their own chats
CREATE POLICY "Users can update messages in their own chats"
    ON messages FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

-- Users can delete messages from their own chats
CREATE POLICY "Users can delete messages from their own chats"
    ON messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM chats
            WHERE chats.id = messages.chat_id
            AND chats.user_id = auth.uid()
        )
    );

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_chats_updated_at
    BEFORE UPDATE ON chats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Note: Storage bucket 'chatbot-images' needs to be created manually in Supabase Dashboard
-- Storage > Create Bucket > Name: chatbot-images > Public: true

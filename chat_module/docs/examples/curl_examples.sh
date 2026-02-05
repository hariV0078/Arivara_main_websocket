#!/bin/bash

# Chatbot Plugin API - cURL Examples
# Replace YOUR_JWT_TOKEN with your actual JWT token
# Replace API_BASE_URL with your API base URL

API_BASE_URL="https://api.example.com/api"
JWT_TOKEN="YOUR_JWT_TOKEN_HERE"

# Health Check
echo "=== Health Check ==="
curl -X GET "${API_BASE_URL}/health"

# Send a message (create new chat)
echo -e "\n\n=== Send Message (New Chat) ==="
curl -X POST "${API_BASE_URL}/chat" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": null,
    "message": "What is the weather today?",
    "enable_web_scraping": true
  }'

# Send a message (existing chat)
echo -e "\n\n=== Send Message (Existing Chat) ==="
CHAT_ID="123e4567-e89b-12d3-a456-426614174000"
curl -X POST "${API_BASE_URL}/chat" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"${CHAT_ID}\",
    \"message\": \"Tell me more about that\",
    \"enable_web_scraping\": false
  }"

# Send message with image (base64)
echo -e "\n\n=== Send Message with Image ==="
curl -X POST "${API_BASE_URL}/chat" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": null,
    "message": "What is in this image?",
    "images": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
    "enable_web_scraping": false
  }'

# List all chats
echo -e "\n\n=== List Chats ==="
curl -X GET "${API_BASE_URL}/chat/chats?page=1&page_size=20" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Get specific chat with messages
echo -e "\n\n=== Get Chat ==="
curl -X GET "${API_BASE_URL}/chat/chats/${CHAT_ID}" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Create new chat
echo -e "\n\n=== Create Chat ==="
curl -X POST "${API_BASE_URL}/chat/chats" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "heading": "My New Chat",
    "auto_generate_heading": false
  }'

# Update chat heading
echo -e "\n\n=== Update Chat Heading ==="
curl -X PUT "${API_BASE_URL}/chat/chats/${CHAT_ID}/heading" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "heading": "Updated Heading"
  }'

# Delete chat
echo -e "\n\n=== Delete Chat ==="
curl -X DELETE "${API_BASE_URL}/chat/chats/${CHAT_ID}" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Upload image file
echo -e "\n\n=== Upload Image ==="
curl -X POST "${API_BASE_URL}/chat/upload-image" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -F "file=@/path/to/image.png"

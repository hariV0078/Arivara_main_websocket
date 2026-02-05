"""
Chatbot Plugin API - Python Examples
"""

import requests
import base64
from typing import Optional, Dict, Any

API_BASE_URL = "https://api.example.com/api"
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"


class ChatbotClient:
    """Client for interacting with the Chatbot Plugin API."""
    
    def __init__(self, api_url: str, jwt_token: str):
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        response = requests.get(f"{self.api_url}/health")
        return response.json()
    
    def send_message(
        self,
        message: str,
        chat_id: Optional[str] = None,
        images: Optional[list] = None,
        enable_web_scraping: bool = True
    ) -> Dict[str, Any]:
        """Send a message to the chatbot."""
        payload = {
            "message": message,
            "enable_web_scraping": enable_web_scraping
        }
        
        if chat_id:
            payload["chat_id"] = chat_id
        
        if images:
            payload["images"] = images
        
        response = requests.post(
            f"{self.api_url}/chat",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_chats(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get all chats for the user."""
        response = requests.get(
            f"{self.api_url}/chat/chats",
            headers=self.headers,
            params={"page": page, "page_size": page_size}
        )
        response.raise_for_status()
        return response.json()
    
    def get_chat(self, chat_id: str) -> Dict[str, Any]:
        """Get a specific chat with messages."""
        response = requests.get(
            f"{self.api_url}/chat/chats/{chat_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def create_chat(self, heading: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat."""
        payload = {}
        if heading:
            payload["heading"] = heading
        
        response = requests.post(
            f"{self.api_url}/chat/chats",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def update_chat_heading(self, chat_id: str, heading: str) -> Dict[str, Any]:
        """Update chat heading."""
        response = requests.put(
            f"{self.api_url}/chat/chats/{chat_id}/heading",
            headers=self.headers,
            json={"heading": heading}
        )
        response.raise_for_status()
        return response.json()
    
    def delete_chat(self, chat_id: str) -> Dict[str, Any]:
        """Delete a chat."""
        response = requests.delete(
            f"{self.api_url}/chat/chats/{chat_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def upload_image(self, image_path: str) -> Dict[str, Any]:
        """Upload an image file."""
        headers = {
            "Authorization": f"Bearer {self.headers['Authorization'].split(' ')[1]}"
        }
        
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{self.api_url}/chat/upload-image",
                headers=headers,
                files=files
            )
        response.raise_for_status()
        return response.json()
    
    def image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 string."""
        with open(image_path, 'rb') as f:
            image_data = f.read()
            base64_str = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{base64_str}"


# Example usage
if __name__ == "__main__":
    client = ChatbotClient(API_BASE_URL, JWT_TOKEN)
    
    # Health check
    print("Health Check:")
    print(client.health_check())
    print()
    
    # Send a message
    print("Sending message...")
    response = client.send_message(
        message="What's the weather today?",
        enable_web_scraping=True
    )
    print(f"Response: {response['data']['message']}")
    print(f"Chat ID: {response['data']['chat_id']}")
    print()
    
    # Get all chats
    print("Getting chats...")
    chats = client.get_chats()
    print(f"Total chats: {chats['total']}")
    for chat in chats['data']:
        print(f"  - {chat['heading']} ({chat['id']})")
    print()
    
    # Get specific chat
    if chats['data']:
        chat_id = chats['data'][0]['id']
        print(f"Getting chat {chat_id}...")
        chat = client.get_chat(chat_id)
        print(f"Messages: {len(chat['data']['messages'])}")
        print()
    
    # Upload image
    # print("Uploading image...")
    # image_result = client.upload_image("path/to/image.png")
    # print(f"Image URL: {image_result['data']['url']}")
    # print()
    
    # Send message with image
    # print("Sending message with image...")
    # base64_image = client.image_to_base64("path/to/image.png")
    # response = client.send_message(
    #     message="What's in this image?",
    #     images=[base64_image],
    #     enable_web_scraping=False
    # )
    # print(f"Response: {response['data']['message']}")

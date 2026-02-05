import base64
import io
from typing import List, Optional
from uuid import uuid4
from PIL import Image
from supabase import Client
from app.config import settings
from app.services.supabase_service import SupabaseService


class ImageService:
    def __init__(self, supabase_service: SupabaseService):
        self.supabase_service = supabase_service
        self.bucket_name = settings.supabase_storage_bucket
    
    async def upload_image(self, image_bytes: bytes, user_id: str) -> str:
        """
        Upload image to Supabase Storage and return the public URL.
        """
        try:
            # Validate image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Generate unique filename
            file_extension = img.format.lower() if img.format else "png"
            filename = f"{user_id}/{uuid4()}.{file_extension}"
            
            # Upload to Supabase Storage
            self.supabase_service.client.storage.from_(self.bucket_name).upload(
                path=filename,
                file=image_bytes,
                file_options={"content-type": f"image/{file_extension}"}
            )
            
            # Get public URL
            url_result = self.supabase_service.client.storage.from_(self.bucket_name).get_public_url(filename)
            
            return url_result
        except Exception as e:
            raise Exception(f"Failed to upload image: {str(e)}")
    
    async def upload_multiple_images(self, image_bytes_list: List[bytes], user_id: str) -> List[str]:
        """
        Upload multiple images and return their URLs.
        """
        urls = []
        for image_bytes in image_bytes_list:
            url = await self.upload_image(image_bytes, user_id)
            urls.append(url)
        return urls
    
    def process_base64_images(self, base64_images: List[str]) -> List[bytes]:
        """
        Convert base64 encoded images to bytes.
        """
        image_bytes_list = []
        for base64_img in base64_images:
            try:
                # Remove data URL prefix if present
                if "," in base64_img:
                    base64_img = base64_img.split(",")[1]
                
                image_bytes = base64.b64decode(base64_img)
                
                # Validate it's an image
                Image.open(io.BytesIO(image_bytes))
                
                image_bytes_list.append(image_bytes)
            except Exception as e:
                raise Exception(f"Invalid image format: {str(e)}")
        
        return image_bytes_list
    
    def get_image_data_url(self, image_url: str) -> str:
        """
        Convert image URL to data URL format for OpenAI API.
        For Supabase storage URLs, we can use them directly or convert to base64.
        """
        # For now, return the URL as-is (OpenAI supports URLs)
        # If needed, we can fetch and convert to base64 data URL
        return image_url

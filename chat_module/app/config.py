from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union
import os


class Settings(BaseSettings):
    # OpenAI / Gemini Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Provider: 'openai' or 'gemini'
    chat_provider: str = os.getenv("CHAT_PROVIDER", "gemini")
    
    # Supabase Configuration - Uses same env variables as main backend
    # These are read from environment, not from separate .env file
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_storage_bucket: str = "chatbot-images"
    
    # Web Scraping APIs
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")
    
    # Application Configuration
    api_prefix: str = "/api"
    cors_origins: Union[str, List[str]] = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    environment: str = "development"
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Split comma-separated string and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


settings = Settings()

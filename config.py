"""
Configuration settings for the FastAPI server
"""
import os
from typing import Optional

class Settings:
    """Application settings"""
    
    def __init__(self):
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = os.getenv("DEBUG", "False").lower() == "true"
        
    def validate(self) -> bool:
        """Validate that all required settings are present"""
        if not self.gemini_api_key:
            print("Error: GEMINI_API_KEY environment variable is not set")
            return False
        return True

settings = Settings()

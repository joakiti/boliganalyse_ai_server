import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from the project root *relative to this file's location*
# Adjust path if necessary based on where you run the app from locally
# Go up three levels from core/ -> app/ -> src/ -> project root
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)


# print(f"Loading .env from: {dotenv_path}") # Debug print
# print(f"Supabase URL from env: {os.getenv('SUPABASE_URL')}") # Debug print

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PROJECT_NAME: str = "BoligAnalyse API"
    API_V1_STR: str = "/api/v1"

    # Supabase Config - Ensure these are set in your environment!
    # Render uses Environment Variables in the dashboard
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "YOUR_DEFAULT_SUPABASE_URL")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "YOUR_DEFAULT_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "YOUR_DEFAULT_SERVICE_KEY")
    # Add JWT Secret only if doing manual verification (less common now)
    # SUPABASE_JWT_SECRET: Optional[str] = os.getenv("SUPABASE_JWT_SECRET", None)

    # AI Service Config (Example for Claude - add yours)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    # OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY", None)

    # Add other settings as needed

    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=dotenv_path,  # Specify .env file path
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'  # Ignore extra fields from env
    )


settings = Settings()

# Basic validation (prints warnings during startup if not configured)
if not settings.SUPABASE_URL or "YOUR_DEFAULT" in settings.SUPABASE_URL:
    print("WARNING: SUPABASE_URL is not configured properly.")
if not settings.SUPABASE_ANON_KEY or "YOUR_DEFAULT" in settings.SUPABASE_ANON_KEY:
    print("WARNING: SUPABASE_ANON_KEY is not configured properly.")
if not settings.SUPABASE_SERVICE_ROLE_KEY or "YOUR_DEFAULT" in settings.SUPABASE_SERVICE_ROLE_KEY:
    print("WARNING: SUPABASE_SERVICE_ROLE_KEY is not configured properly.")

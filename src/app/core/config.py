import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PROJECT_NAME: str = "BoligAnalyse API"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "YOUR_DEFAULT_SUPABASE_URL")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "YOUR_DEFAULT_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "YOUR_DEFAULT_SERVICE_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY", None)
    model_config = SettingsConfigDict(
        env_file=dotenv_path,
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )


settings = Settings()

if not settings.SUPABASE_URL or "YOUR_DEFAULT" in settings.SUPABASE_URL:
    print("WARNING: SUPABASE_URL is not configured properly.")
if not settings.SUPABASE_ANON_KEY or "YOUR_DEFAULT" in settings.SUPABASE_ANON_KEY:
    print("WARNING: SUPABASE_ANON_KEY is not configured properly.")
if not settings.SUPABASE_SERVICE_ROLE_KEY or "YOUR_DEFAULT" in settings.SUPABASE_SERVICE_ROLE_KEY:
    print("WARNING: SUPABASE_SERVICE_ROLE_KEY is not configured properly.")

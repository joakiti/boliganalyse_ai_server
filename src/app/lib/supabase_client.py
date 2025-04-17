import logging
from typing import Optional

from supabase import acreate_client, AsyncClient, AsyncClientOptions
from src.app.core.config import settings

logger = logging.getLogger(__name__)

_supabase_admin_client: Optional[AsyncClient] = None


async def get_supabase_admin_client() -> AsyncClient:
    global _supabase_admin_client

    if _supabase_admin_client is None:
        logger.info("Initializing Supabase Admin Client...")
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase URL or Service Role Key is missing!")
            raise ValueError("Supabase credentials missing for admin client.")

        try:
            _supabase_admin_client = await acreate_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
                options=AsyncClientOptions(
                    postgrest_client_timeout=5,  # Increased timeout for potentially slower DB ops
                )
            )
            logger.info("Supabase Admin Client Initialized.")

        except Exception as e:
            logger.error(f"Failed to initialize Supabase Admin Client: {e}", exc_info=True)
            raise

    return _supabase_admin_client

import os
from supabase import acreate_client, AsyncClient
from supabase.lib.client_options import ClientOptions
import logging
from typing import Optional # Import Optional

# Import settings from the correct location
from src.app.core.config import settings

logger = logging.getLogger(__name__)

# Global variable to hold the singleton client instance
_supabase_admin_client: Optional[AsyncClient] = None # Use Optional

async def get_supabase_admin_client() -> AsyncClient:
    """Provides a singleton Supabase admin client instance."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        logger.info("Initializing Supabase Admin Client...")
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase URL or Service Role Key is missing!")
            raise ValueError("Supabase credentials missing for admin client.")

        try:
            # Use create_client which is now async
            _supabase_admin_client = await acreate_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
                options=ClientOptions(
                    postgrest_client_timeout=30, # Increased timeout for potentially slower DB ops
                )
            )
            logger.info("Supabase Admin Client Initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase Admin Client: {e}", exc_info=True)
            raise
    # logger.debug("Reusing Supabase Admin Client instance.")
    return _supabase_admin_client

async def get_supabase_user_client(access_token: str) -> AsyncClient:
    """Creates a Supabase client authenticated as the user."""
    logger.debug(f"Creating Supabase User Client...")
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.error("Supabase URL or Anon Key is missing for user client!")
        raise ValueError("Supabase credentials missing for user client.")

    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        options = ClientOptions(
             postgrest_client_timeout=10,
             global_headers=headers
        )
        # Create a new client instance for each user request
        # Use create_client which is now async
        user_client = await create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
            options=options
        )
        logger.debug("Supabase User Client created.")
        return user_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase User Client: {e}", exc_info=True)
        raise

async def shutdown_supabase_clients():
    """Gracefully shut down client connections."""
    global _supabase_admin_client
    if _supabase_admin_client:
        try:
            # Use aclose() for async client
            await _supabase_admin_client.aclose()
            logger.info("Supabase admin client closed.")
            _supabase_admin_client = None
        except Exception as e:
             logger.error(f"Error closing Supabase admin client: {e}", exc_info=True)
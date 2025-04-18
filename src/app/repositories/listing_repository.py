import uuid
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, cast, TypeVar, Union
from postgrest import APIResponse
from supabase import AsyncClient

from src.app.lib.supabase_client import get_supabase_admin_client
from src.app.schemas.status import AnalysisStatus
from src.app.schemas.database import DatabaseSchema, TableName, SCHEMA_CONFIG, Listing

logger = logging.getLogger(__name__)


class ListingRepository:
    """Repository for managing apartment listings in the database."""

    TABLE_NAME = TableName.APARTMENT_LISTINGS.value
    SCHEMA_NAME = DatabaseSchema.PRIVATE.value

    def __init__(self, supabase_client: Optional[AsyncClient] = None):
        self.supabase = supabase_client if supabase_client else None

    async def initialize(self):
        if self.supabase is None:
            self.supabase = await get_supabase_admin_client()
            if self.supabase is None:
                raise RuntimeError("Failed to initialize Supabase client")

    async def find_by_id(self, listing_id: uuid.UUID) -> Optional[Listing]:
        await self.initialize()
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        try:
            # Use APIResponse[Any] instead of specifying exact response structure
            response: APIResponse[Any] = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .select("*") \
                .eq("id", str(listing_id)) \
                .limit(1) \
                .execute()

            if response.data and len(response.data) > 0:
                # Type check the data at runtime
                if isinstance(response.data, list) and len(response.data) > 0:
                    return Listing.from_db_dict(response.data[0])
            return None
        except Exception as e:
            logger.error(f"Error finding listing by ID {listing_id}: {e}")
            raise

    async def find_by_normalized_url(self, normalized_url: str) -> Optional[Listing]:
        await self.initialize()
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        try:
            # Use APIResponse[Any] for flexibility
            response: APIResponse[Any] = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .select("*") \
                .eq("normalized_url", normalized_url) \
                .limit(1) \
                .execute()

            if response.data and len(response.data) > 0:
                if isinstance(response.data, list) and len(response.data) > 0:
                    return Listing.from_db_dict(response.data[0])
            return None
        except Exception as e:
            logger.error(f"Error finding listing by normalized URL {normalized_url}: {e}")
            raise

    async def save(self, listing: Listing) -> Listing:
        """
        Save a listing - creates a new one if id is None, otherwise updates existing.

        Args:
            listing: The Listing entity to save

        Returns:
            The saved Listing with updated fields
        """
        if not listing.id:
            return await self.create(listing)
        else:
            return await self.update(listing)

    async def create(self, listing: Listing) -> Listing:
        """
        Create a new listing.

        Args:
            listing: The Listing entity to create

        Returns:
            The created Listing with ID and timestamps
        """
        await self.initialize()
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        db_dict = listing.to_db_dict()

        try:
            # Use APIResponse[Any] for flexibility
            response: APIResponse[Any] = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .insert(db_dict) \
                .execute()

            if response.data and len(response.data) > 0:
                if isinstance(response.data, list) and len(response.data) > 0:
                    return Listing.from_db_dict(response.data[0])
            raise Exception("Failed to create listing, no data returned")

        except Exception as e:
            logger.error(f"Error creating listing for URL {listing.url}: {e}")
            raise

    async def update(self, listing: Listing) -> Listing:
        """
        Update an existing listing.

        Args:
            listing: The Listing entity to update

        Returns:
            The updated Listing
        """
        await self.initialize()
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        listing.updated_at = datetime.now(timezone.utc)
        db_dict = listing.to_db_dict()

        try:
            # Use APIResponse[Any] for flexibility
            response: APIResponse[Any] = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(db_dict) \
                .eq("id", str(listing.id)) \
                .execute()

            if response.data and len(response.data) > 0:
                if isinstance(response.data, list) and len(response.data) > 0:
                    return Listing.from_db_dict(response.data[0])
            raise Exception(f"Failed to update listing {listing.id}, no data returned")
        except Exception as e:
            logger.error(f"Error updating listing {listing.id}: {e}")
            raise

    async def update_status(self, listing_id: uuid.UUID, status: AnalysisStatus) -> Listing:
        """
        Update the status of an existing listing.

        Args:
            listing_id: The ID of the listing to update.
            status: The new AnalysisStatus value.

        Returns:
            The updated Listing object.
        """
        await self.initialize()
        if not self.supabase:
            raise RuntimeError("Supabase client not initialized")

        update_payload = {
            'status': status.value,
            'updated_at': datetime.now(timezone.utc)
        }

        try:
            # Use APIResponse[Any] for flexibility
            response: APIResponse[Any] = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(update_payload) \
                .eq("id", str(listing_id)) \
                .execute()

            if response.data and len(response.data) > 0:
                if isinstance(response.data, list) and len(response.data) > 0:
                    return Listing.from_db_dict(response.data[0])
            raise Exception(f"Failed to update status for listing {listing_id} to {status.value}. Supabase returned no data.")
        except Exception as e:
            logger.error(f"Error updating status for listing {listing_id} to {status.value}: {e}")
            raise

    async def create_or_get_listing(self, url: str, normalized_url: str) -> Listing:
        """
        Find a listing by normalized URL or create a new one.
        """
        existing_listing = await self.find_by_normalized_url(normalized_url)
        if existing_listing:
            return existing_listing

        new_listing = Listing(
            url=url,
            normalized_url=normalized_url,
            status=AnalysisStatus.PENDING
        )
        return await self.create(new_listing)
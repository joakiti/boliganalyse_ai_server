import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from supabase import Client  # Import Client for type hinting

from src.app.lib.supabase_client import get_supabase_admin_client
from src.app.schemas.status import AnalysisStatus
from src.app.schemas.database import DatabaseSchema, TableName, SCHEMA_CONFIG, Listing

logger = logging.getLogger(__name__)


class ListingRepository:
    """Repository for managing apartment listings in the database."""
    
    TABLE_NAME = TableName.APARTMENT_LISTINGS.value
    SCHEMA_NAME = DatabaseSchema.PRIVATE.value

    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client if supabase_client else None

    async def initialize(self):
        if self.supabase is None:
            self.supabase = await get_supabase_admin_client()

    async def find_by_id(self, listing_id: uuid.UUID) -> Optional[Listing]:
        await self.initialize()
        try:
            response = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .select("*") \
                .eq("id", str(listing_id)) \
                .limit(1) \
                .execute()
            
            if response.data:
                return Listing.from_db_dict(response.data[0])
            return None
        except Exception as e:
            logger.error(f"Error finding listing by ID {listing_id}: {e}")
            raise

    async def find_by_normalized_url(self, normalized_url: str) -> Optional[Listing]:
        await self.initialize()
        try:
            response = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .select("*") \
                .eq("normalized_url", normalized_url) \
                .limit(1) \
                .execute()
                
            if response.data:
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
        
        # Set timestamps if not provided
        now = datetime.now(timezone.utc).isoformat()
        if not listing.created_at:
            listing.created_at = now
        if not listing.updated_at:
            listing.updated_at = now
            
        # Convert to database dictionary
        db_dict = listing.to_db_dict()
        
        try:
            response = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .insert(db_dict) \
                .execute()
                
            if response.data:
                return Listing.from_db_dict(response.data[0])
            else:
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
        
        # Always update timestamp
        listing.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Convert to database dictionary
        db_dict = listing.to_db_dict()
        
        try:
            response = await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(db_dict) \
                .eq("id", str(listing.id)) \
                .execute()
                
            if response.data:
                return Listing.from_db_dict(response.data[0])
            else:
                raise Exception(f"Failed to update listing {listing.id}, no data returned")
        except Exception as e:
            logger.error(f"Error updating listing {listing.id}: {e}")
            raise
            
    async def update_fields(self, listing_id: uuid.UUID, **kwargs) -> None:
        """
        Update specific fields of a listing.

        Args:
            listing_id: The UUID of the listing to update
            **kwargs: Fields to update
        """
        await self.initialize()
        
        # Ensure we have something to update
        if not kwargs:
            return
            
        # Convert status enum to value if provided
        if "status" in kwargs and isinstance(kwargs["status"], AnalysisStatus):
            kwargs["status"] = kwargs["status"].value
            
        # Always update timestamp
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        try:
            await self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(kwargs) \
                .eq("id", str(listing_id)) \
                .execute()
        except Exception as e:
            logger.error(f"Error updating listing fields {listing_id}: {e}")
            raise

    async def create_or_get_listing(self, url: str, normalized_url: str) -> Listing:
        """
        Find a listing by normalized URL or create a new one.
        """
        existing_listing = await self.find_by_normalized_url(normalized_url)
        if existing_listing:
            return existing_listing

        # Create a new listing
        new_listing = Listing(
            url=url,
            normalized_url=normalized_url,
            status=AnalysisStatus.PENDING
        )
        return await self.create(new_listing)
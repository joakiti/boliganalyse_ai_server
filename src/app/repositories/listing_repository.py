import uuid
from typing import Optional, Dict, Any
from supabase_py_async import AsyncClient
from datetime import datetime, timezone

# Assuming get_supabase_client is available in this path
# If not, this import will need adjustment based on the actual location.
from src.app.lib.supabase_client import get_supabase_client


class ListingRepository:
    """
    Handles database operations for apartment listings in Supabase.
    Uses the 'private.apartment_listings' table.
    """
    TABLE_NAME = "private.apartment_listings"

    def __init__(self, supabase_client: Optional[AsyncClient] = None):
        """
        Initializes the repository with an optional Supabase client.
        If no client is provided, it gets one using get_supabase_client.
        """
        self.supabase = supabase_client or get_supabase_client()

    async def find_by_normalized_url(self, normalized_url: str) -> Optional[Dict[str, Any]]:
        """
        Finds a listing by its normalized URL.

        Args:
            normalized_url: The normalized URL of the listing.

        Returns:
            A dictionary representing the listing if found, otherwise None.
        """
        try:
            response = await self.supabase.table(self.TABLE_NAME)\
                .select("*")\
                .eq("normalized_url", normalized_url)\
                .limit(1)\
                .execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            # TODO: Add proper logging
            print(f"Error finding listing by normalized URL {normalized_url}: {e}")
            raise

    async def create_listing(self, url: str, normalized_url: str, provider: str) -> Dict[str, Any]:
        """
        Creates a new listing record with initial status 'pending'.

        Args:
            url: The original URL of the listing.
            normalized_url: The normalized URL.
            provider: The name of the provider (e.g., 'Boligsiden', 'Danbolig').

        Returns:
            A dictionary representing the newly created listing.
        """
        listing_data = {
            "url": url,
            "normalized_url": normalized_url,
            "provider": provider,
            "status": "pending", # Initial status
            "status_message": "Analysis request received",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = await self.supabase.table(self.TABLE_NAME)\
                .insert(listing_data)\
                .execute()
            if response.data:
                return response.data[0]
            else:
                # TODO: Improve error handling/logging
                raise Exception("Failed to create listing, no data returned.")
        except Exception as e:
            print(f"Error creating listing for URL {url}: {e}")
            raise

    async def update_status(self, listing_id: uuid.UUID, status: str, status_message: Optional[str] = None) -> None:
        """
        Updates the status and status message of a listing.

        Args:
            listing_id: The UUID of the listing to update.
            status: The new status string (e.g., 'fetching_html', 'completed').
            status_message: An optional message describing the current status.
        """
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status_message is not None:
            update_data["status_message"] = status_message

        try:
            await self.supabase.table(self.TABLE_NAME)\
                .update(update_data)\
                .eq("id", str(listing_id))\
                .execute()
        except Exception as e:
            print(f"Error updating status for listing {listing_id} to {status}: {e}")
            # Decide if we should raise or just log
            # raise

    async def set_error_status(self, listing_id: uuid.UUID, error_message: str, status: str = "error") -> None:
        """
        Sets the listing status to an error state.

        Args:
            listing_id: The UUID of the listing.
            error_message: The error message to record.
            status: The specific error status code (defaults to 'error').
        """
        # Ensure status reflects an error state if a specific one isn't provided
        if status not in ["error", "invalid_url", "timeout"]:
            status = "error"

        await self.update_status(listing_id, status, status_message=error_message)

    async def save_analysis_result(self, listing_id: uuid.UUID, analysis_result: Dict[str, Any], status: str = "completed") -> None:
        """
        Saves the analysis result JSON and sets the status to 'completed'.

        Args:
            listing_id: The UUID of the listing.
            analysis_result: The dictionary containing the analysis results.
            status: The final status (defaults to 'completed').
        """
        update_data = {
            "analysis_result": analysis_result,
            "status": status,
            "status_message": "Analysis successfully completed",
            "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.supabase.table(self.TABLE_NAME)\
                .update(update_data)\
                .eq("id", str(listing_id))\
                .execute()
        except Exception as e:
            print(f"Error saving analysis result for listing {listing_id}: {e}")
            # Consider setting error status here?
            # await self.set_error_status(listing_id, f"Failed to save result: {e}")
            raise

    async def update_listing_metadata(self, listing_id: uuid.UUID, metadata: Dict[str, Any]) -> None:
        """
        Updates metadata fields for a listing (e.g., address, price).
        Does not change the status.

        Args:
            listing_id: The UUID of the listing.
            metadata: A dictionary containing metadata fields to update.
                      Keys should match column names in the table (e.g., 'address', 'price').
        """
        if not metadata:
            return # Nothing to update

        # Ensure updated_at is always set
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            await self.supabase.table(self.TABLE_NAME)\
                .update(metadata)\
                .eq("id", str(listing_id))\
                .execute()
        except Exception as e:
            print(f"Error updating metadata for listing {listing_id}: {e}")
            # Decide if we should raise or just log
            # raise
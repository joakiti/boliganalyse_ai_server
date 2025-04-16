import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from supabase import Client  # Import Client for type hinting

# Assuming get_supabase_client is available in this path
# If not, this import will need adjustment based on the actual location.
# Assuming get_supabase_client is updated or replaced to return a sync client
from src.app.lib.supabase_client import get_supabase_admin_client
from src.app.schemas.status import AnalysisStatus


class ListingRepository:
    """
    Handles database operations for apartment listings in Supabase.
    Uses the 'private.apartment_listings' table.
    """
    # Use the correct table name as defined in the tests
    TABLE_NAME = "listings"
    SCHEMA_NAME = "private"  # Define schema separately

    def __init__(self, supabase_client: Optional[Client] = None):
        """
        Initializes the repository with an optional Supabase client.
        If no client is provided, it gets one using get_supabase_client.
        """
        self.supabase = supabase_client or get_supabase_admin_client()

    def find_by_normalized_url(self, normalized_url: str) -> Optional[Dict[str, Any]]:
        """
        Finds a listing by its normalized URL.

        Args:
            normalized_url: The normalized URL of the listing.

        Returns:
            A dictionary representing the listing if found, otherwise None.
        """
        try:
            # Use schema() method for specifying schema
            response = self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .select("*") \
                .eq("normalized_url", normalized_url) \
                .limit(1) \
                .execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            # TODO: Add proper logging
            print(f"Error finding listing by normalized URL {normalized_url}: {e}")
            raise

    # Removed provider argument as it wasn't used in the test creation logic
    # and the schema might not have it. Add back if needed.
    def create_listing(self, url: str, normalized_url: str) -> Dict[str, Any]:
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
            # "provider": provider, # Removed provider
            "status": "PENDING",  # Match AnalysisStatus enum value used in tests
            # "status_message": "Analysis request received", # Remove if not in schema or handled differently
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .insert(listing_data) \
                .execute()
            if response.data:
                return response.data[0]
            else:
                # TODO: Improve error handling/logging
                raise Exception("Failed to create listing, no data returned.")
        except Exception as e:
            print(f"Error creating listing for URL {url}: {e}")
            raise

    # Changed status type hint to AnalysisStatus to match test usage
    from src.app.schemas.status import AnalysisStatus  # Add this import at the top if not already there

    def update_status(self, listing_id: uuid.UUID, status: AnalysisStatus,
                      status_message: Optional[str] = None) -> None:
        """
        Updates the status and status message of a listing.

        Args:
            listing_id: The UUID of the listing to update.
            status: The new status string (e.g., 'fetching_html', 'completed').
            status_message: An optional message describing the current status.
        """
        update_data = {
            "status": status.value,  # Use enum value
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status_message is not None:
            update_data["status_message"] = status_message

        try:
            self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(update_data) \
                .eq("id", str(listing_id)) \
                .execute()
        except Exception as e:
            print(f"Error updating status for listing {listing_id} to {status}: {e}")
            # Decide if we should raise or just log
            # raise

    # Changed status type hint to AnalysisStatus
    # Changed error_message type hint to Exception to match test usage
    def set_error_status(self, listing_id: uuid.UUID, status: AnalysisStatus, error_instance: Exception) -> None:
        """
        Sets the listing status to an error state.

        Args:
            listing_id: The UUID of the listing.
            status: The error status enum value (e.g., AnalysisStatus.SCRAPING_FAILED).
            error_instance: The exception instance that occurred.
        """
        error_message = f"{type(error_instance).__name__}: {error_instance}"
        update_data = {
            "status": status.value,
            "error_message": error_message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(update_data) \
                .eq("id", str(listing_id)) \
                .execute()
        except Exception as e:
            print(f"Error setting error status for listing {listing_id}: {e}")
            # raise # Optional: re-raise

    # Changed status type hint to AnalysisStatus
    def save_analysis_result(self, listing_id: uuid.UUID, analysis_result: Dict[str, Any],
                             status: AnalysisStatus = AnalysisStatus.COMPLETED) -> None:
        """
        Saves the analysis result JSON and sets the status to 'completed'.

        Args:
            listing_id: The UUID of the listing.
            analysis_result: The dictionary containing the analysis results.
            status: The final status enum value (defaults to AnalysisStatus.COMPLETED).
        """
        update_data = {
            "analysis_result": analysis_result,  # Ensure this column exists and is JSONB type
            "status": status.value,
            # "status_message": "Analysis successfully completed", # Remove if not used
            # "analysis_completed_at": datetime.now(timezone.utc).isoformat(), # Remove if not in schema
            "error_message": None,  # Clear previous errors
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(update_data) \
                .eq("id", str(listing_id)) \
                .execute()
        except Exception as e:
            print(f"Error saving analysis result for listing {listing_id}: {e}")
            # Consider setting error status here?
            # await self.set_error_status(listing_id, f"Failed to save result: {e}")
            raise

    def update_listing_metadata(self, listing_id: uuid.UUID, metadata: Dict[str, Any]) -> None:
        """
        Updates metadata fields for a listing (e.g., address, price).
        Does not change the status.

        Args:
            listing_id: The UUID of the listing.
            metadata: A dictionary containing metadata fields to update.
                      Keys should match column names in the table (e.g., 'address', 'price').
        """
        if not metadata:
            return  # Nothing to update

        # Ensure updated_at is always set
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            self.supabase.schema(self.SCHEMA_NAME).table(self.TABLE_NAME) \
                .update(metadata) \
                .eq("id", str(listing_id)) \
                .execute()
        except Exception as e:
            print(f"Error updating metadata for listing {listing_id}: {e}")
            # Decide if we should raise or just log
            # raise

    async def create_or_get_listing(self, url: str, normalized_url: str) -> Dict[str, Any]:
        """
        Finds a listing by its normalized URL or creates a new one if it doesn't exist.

        Args:
            url: The original URL of the listing.
            normalized_url: The normalized URL of the listing.

        Returns:
            A dictionary representing the listing.
        """
        # First try to find existing listing
        existing_listing = self.find_by_normalized_url(normalized_url)
        if existing_listing:
            return existing_listing

        # If not found, create a new listing
        return self.create_listing(url, normalized_url)

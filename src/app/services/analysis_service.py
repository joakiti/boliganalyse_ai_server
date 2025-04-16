import asyncio
import logging
from typing import Dict, Any
from uuid import UUID

from src.app.lib.url_validation import validate_listing_url
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.analyze import AnalysisRequest, AnalysisStatus
from .ai_analyzer import AIAnalyzerService
from ..lib.providers import provider_registry

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


class AnalysisService:
    def __init__(self):
        self.listing_repository = ListingRepository()
        self.ai_analyzer = AIAnalyzerService()

    async def prepare_analysis(self, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Prepare and validate the analysis request.
        
        Args:
            request: The analysis request containing the URL
            
        Returns:
            Dictionary with listing ID and status
            
        Raises:
            ValueError: If the URL is invalid or unsupported
        """
        # Validate URL
        validation_result = validate_listing_url(request.url)
        if not validation_result["valid"]:
            raise ValueError(validation_result["error"])

        # Generate normalized URL if not provided
        normalized_url = str(request.url).replace("https://", "").replace("http://", "")

        # Get or create listing
        listing = await self.listing_repository.create_or_get_listing(
            url=request.url,
            normalized_url=normalized_url
        )

        return {
            "listing_id": str(listing.id),
            "status": AnalysisStatus.PENDING
        }

    async def start_analysis_task(self, listing_id: UUID) -> None:
        """
        Start the analysis task for a listing.
        
        Args:
            listing_id: The ID of the listing to analyze
        """
        try:
            # Get listing
            listing = await self.listing_repository.find_by_id(listing_id)
            if not listing:
                logger.error(f"Listing {listing_id} not found")
                return

            # Get content from provider
            provider = provider_registry.get_provider_for_content(listing.url, listing.html_content_primary)
            if not provider:
                raise ValueError(f"Unsupported URL or content: No provider could handle {listing.url}")

            # Get content
            html_content_primary = await provider.get_content(listing.url)
            html_content_secondary = await provider.get_secondary_content(
                listing.url) if provider.supports_secondary_content else None

            # Update listing with content
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                html_content_primary=html_content_primary,
                html_content_secondary=html_content_secondary
            )

            # Start AI analysis
            analysis_result = await self.ai_analyzer.analyze_multiple_texts(
                primary_text=html_content_primary,
                secondary_text=html_content_secondary
            )

            # Update listing with analysis result
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                analysis_result=analysis_result,
                status=AnalysisStatus.COMPLETED
            )

        except Exception as e:
            logger.error(f"[{listing_id}] Error during analysis task: {e}", exc_info=True)
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                status=AnalysisStatus.FAILED,
                error_message=str(e)
            )

    async def submit_analysis(self, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Submit a new analysis request.
        
        Args:
            request: The analysis request containing the URL
            
        Returns:
            Dictionary with listing ID and status
        """
        try:
            # Prepare analysis
            result = await self.prepare_analysis(request)
            listing_id = UUID(result["listing_id"])

            # Start analysis task in the background
            asyncio.create_task(self.start_analysis_task(listing_id))

            return result

        except ValueError as e:
            # Handle validation errors
            logger.warning(f"Validation error: {e}")
            raise

        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Error submitting analysis: {e}", exc_info=True)
            raise RuntimeError("Failed to submit analysis request") from e

    async def get_analysis_status(self, listing_id: UUID) -> Dict[str, Any]:
        """
        Get the status of an analysis.
        
        Args:
            listing_id: The ID of the listing to check
            
        Returns:
            Dictionary with status and result if available
        """
        try:
            listing = await self.listing_repository.find_by_id(listing_id)
            if not listing:
                raise ValueError(f"Listing {listing_id} not found")

            result = {
                "status": listing.status,
                "listing_id": str(listing.id)
            }

            if listing.analysis_result:
                result["result"] = listing.analysis_result

            if listing.error_message:
                result["error"] = listing.error_message

            return result

        except ValueError as e:
            # Handle not found errors
            logger.warning(f"Listing not found: {e}")
            raise

        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Error getting analysis status: {e}", exc_info=True)
            raise RuntimeError("Failed to get analysis status") from e


async def get_analysis_status_and_result(listing_id: UUID, repository: ListingRepository) -> Dict[str, Any]:
    """Fetches the current status, analysis result, and other relevant data for a listing."""
    logger.info(f"Fetching status and data for listing ID: {listing_id}")
    try:
        listing_data = await repository.get_listing_details(listing_id)
        if not listing_data:
            raise ValueError(f"Listing with ID {listing_id} not found.")
        # Ensure status is returned as string value for API response consistency
        if 'status' in listing_data and isinstance(listing_data['status'], AnalysisStatus):
            listing_data['status'] = listing_data['status'].value
        return listing_data
    except ValueError as ve:  # Catch not found specifically
        logger.warning(f"Value error fetching status for {listing_id}: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Database error fetching status for listing {listing_id}: {e}", exc_info=True)
        raise Exception(f"Database error fetching status: {e}") from e

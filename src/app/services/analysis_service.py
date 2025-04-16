import logging
from typing import Dict, Any, Optional
from uuid import UUID

from src.app.lib.url_utils import normalize_url
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

    async def submit_analysis(self, request: AnalysisRequest, background_tasks=None) -> Dict[str, Any]:
        """
        Validate URL, normalize it, and create or get a listing in the database.
        
        Args:
            request: The analysis request containing the URL
            background_tasks: Optional FastAPI BackgroundTasks object
            
        Returns:
            Dictionary with listing ID and status
            
        Raises:
            ValueError: If the URL is invalid or unsupported
        """
        try:
            # Validate URL
            validation_result = validate_listing_url(str(request.url))
            if not validation_result["valid"]:
                raise ValueError(validation_result["error"])

            # Generate normalized URL using the proper URL normalization utility
            url_str = str(request.url)
            normalized_url = normalize_url(url_str)
            if not normalized_url:
                raise ValueError("Could not normalize URL")

            # Get or create listing
            listing = await self.listing_repository.create_or_get_listing(
                url=url_str,
                normalized_url=normalized_url
            )
            
            # If background_tasks is provided, add the analysis task
            if background_tasks is not None:
                background_tasks.add_task(self.start_analysis_task, UUID(listing["id"]))

            return {
                "listing_id": listing["id"],
                "status": AnalysisStatus.PENDING,
                "message": "Analysis request submitted successfully"
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            # Log and wrap other errors
            logger.error(f"Error submitting analysis: {e}", exc_info=True)
            raise RuntimeError(f"Failed to submit analysis request: {e}")

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
            provider = provider_registry.get_provider_for_content(listing["url"], listing.get("html_content_primary"))
            if not provider:
                raise ValueError(f"Unsupported URL or content: No provider could handle {listing['url']}")

            # Get content
            html_content_primary = await provider.get_content(listing["url"])
            html_content_secondary = await provider.get_secondary_content(
                listing["url"]) if provider.supports_secondary_content else None

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
                "status": listing["status"],
                "listing_id": str(listing["id"])
            }

            if listing.get("analysis_result"):
                result["result"] = listing["analysis_result"]

            if listing.get("error_message"):
                result["error"] = listing["error_message"]

            return result

        except ValueError as e:
            # Handle not found errors
            logger.warning(f"Listing not found: {e}")
            raise

        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Error getting analysis status: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get analysis status: {e}")
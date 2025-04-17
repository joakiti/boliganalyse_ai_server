import logging
from typing import Dict, Any, Optional
from uuid import UUID

from src.app.lib.url_utils import normalize_url
from src.app.lib.url_validation import validate_listing_url
from src.app.lib.html_utils import fetch_html_content
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.analyze import AnalysisRequest, AnalysisStatus
from src.app.schemas.database import Listing
from src.app.schemas.parser import ParseResult # Import the new schema
from .ai_analyzer import AIAnalyzerService
from ..lib.providers.provider_registry import get_provider_registry
from ..lib.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


class AnalysisService:
    def __init__(self):
        self.listing_repository = ListingRepository()
        self.ai_analyzer = AIAnalyzerService()
        self.provider_registry = get_provider_registry()

    async def submit_analysis(self, request: AnalysisRequest, background_tasks=None) -> Dict[str, Any]:
        """
        Validate URL, normalize it, create/get listing, and queue analysis task.
        """
        try:
            validation_result = validate_listing_url(str(request.url))
            if not validation_result["valid"]:
                raise ValueError(validation_result["error"])

            url_str = str(request.url)
            normalized_url = normalize_url(url_str)
            if not normalized_url:
                raise ValueError("Could not normalize URL")

            # Get or create listing (starts with PENDING status)
            listing = await self.listing_repository.create_or_get_listing(
                url=url_str,
                normalized_url=normalized_url
            )

            # Only queue if the listing is PENDING (or maybe ERROR?)
            # Avoid re-queueing already processing or completed listings.
            if listing.status in [AnalysisStatus.PENDING, AnalysisStatus.ERROR] or True:
                if background_tasks is not None or True:
                    background_tasks.add_task(self.start_analysis_task, listing.id)
                    logger.info(f"[{listing.id}] Analysis task added to background queue for URL: {listing.url}")
                else:
                    logger.warning(f"[{listing.id}] Background tasks not provided. Analysis will not run automatically.")
            else:
                 logger.info(f"[{listing.id}] Analysis task not queued. Listing status is '{listing.status.value}'.")


            return {
                "listing_id": listing.id,
                "status": listing.status.value, # Return current status
                "message": "Analysis request submitted successfully"
            }
        except Exception as e:
            logger.error(f"Error submitting analysis request for URL {request.url}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to submit analysis request: {e}")


    async def start_analysis_task(self, listing_id: UUID) -> None:
        """Fetches, parses, analyzes, and saves listing data."""
        logger.info(f"[{listing_id}] Starting analysis task.")
        listing: Optional[Listing] = None
        try:
            listing = await self.listing_repository.find_by_id(listing_id)
            if not listing:
                logger.error(f"[{listing_id}] Listing not found. Aborting analysis task.")
                return

            # Set status to PROCESSING immediately
            listing.status = AnalysisStatus.FETCHING_HTML
            listing = await self.listing_repository.save(listing) # Save PROCESSING status

            # --- Primary Fetch & Parse ---
            primary_html = await fetch_html_content(listing.url)
            listing.html_content_primary = primary_html
            provider: Optional[BaseProvider] = self.provider_registry.get_provider_for_content(listing.url)
            if not provider:
                raise ValueError(f"No provider available for primary URL: {listing.url}")
            parse_result_primary: ParseResult = await provider.parse_html(listing.url, primary_html)
            primary_text = parse_result_primary.extracted_text or "" # Use attribute access

            # --- Source Fetch & Parse (Optional) ---
            source_url = parse_result_primary.original_link # Use attribute access
            secondary_text = None
            source_parse_result: Optional[ParseResult] = None # Define type for clarity
            # Ensure source_url is treated as string for comparison if it's a PydanticUrl
            source_url_str = str(source_url) if source_url else None

            if source_url_str and source_url_str != listing.url:
                listing.source_url = source_url_str # Store the string representation
                try:
                    logger.info(f"[{listing_id}] Processing source URL: {source_url_str}")
                    source_html = await fetch_html_content(source_url_str)
                    listing.html_content_secondary = source_html
                    source_provider: Optional[BaseProvider] = self.provider_registry.get_provider_for_content(source_url_str)
                    if source_provider:
                        source_parse_result = await source_provider.parse_html(source_url_str, source_html)
                        # Use attribute access, check if source_parse_result is not None
                        secondary_text = source_parse_result.extracted_text if source_parse_result else None
                    else:
                        logger.warning(f"[{listing_id}] No provider found for source URL: {source_url_str}")
                except Exception as source_error:
                    logger.warning(f"[{listing_id}] Failed to process source URL {source_url}: {source_error}", exc_info=False) # Log less verbosely
                    listing.html_content_secondary = f"Error fetching/parsing source: {source_error}" # Store error info

            # --- AI Analysis ---
            analysis_result = await self.ai_analyzer.analyze_multiple_texts(
                primary_text=primary_text,
                secondary_text=secondary_text
            )
            listing.analysis_result = analysis_result

            # --- Finalize ---
            listing.status = AnalysisStatus.COMPLETED
            listing.error_message = None # Clear any previous error
            await self.listing_repository.save(listing)
            logger.info(f"[{listing_id}] Analysis task completed successfully.")

        except Exception as e:
            logger.error(f"[{listing_id}] Error during analysis task: {e}", exc_info=True)
            if listing:
                try:
                    listing.status = AnalysisStatus.ERROR
                    listing.error_message = str(e)
                    await self.listing_repository.save(listing)
                    logger.info(f"[{listing_id}] Saved listing with ERROR status.")
                except Exception as save_err:
                    logger.critical(f"[{listing_id}] CRITICAL: Failed to save ERROR status after analysis failure: {save_err}", exc_info=True)
            # No else needed, if listing is None, the error is already logged.

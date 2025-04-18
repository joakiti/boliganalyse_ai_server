import logging
from typing import Dict, Any, Optional
from uuid import UUID

from src.app.lib.html_utils import fetch_html_content
from src.app.lib.url_utils import normalize_url
from src.app.lib.url_validation import validate_listing_url
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.analyze import AnalysisRequest, AnalysisStatus
from src.app.schemas.database import Listing
from src.app.schemas.parser import ParseResult  # Import the new schema
from .ai_analyzer import AIAnalyzerService
from ..lib.providers.base_provider import BaseProvider
from ..lib.providers.provider_registry import get_provider_registry

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


class AnalysisService:
    def __init__(self):
        self.listing_repository = ListingRepository()
        self.ai_analyzer = AIAnalyzerService()
        self.provider_registry = get_provider_registry()

    async def submit_analysis(self, request: AnalysisRequest, background_tasks=None) -> Dict[str, Any]:
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
            "status": listing.status.value,  # Return current status
            "message": "Analysis request submitted successfully"
        }

    async def start_analysis_task(self, listing_id: UUID) -> None:
        """Fetches, parses, analyzes, and saves listing data."""
        logger.info(f"[{listing_id}] Starting analysis task.")

        try:
            listing: Listing = await self.listing_repository.find_by_id(listing_id)
            if not listing:
                logger.error(f"[{listing_id}] Listing not found. Aborting analysis task.")
                return

            listing.status = AnalysisStatus.FETCHING_HTML
            listing = await self.listing_repository.save(listing)

            primary_html = await fetch_html_content(listing.url)

            provider: Optional[BaseProvider] = self.provider_registry.get_provider_for_content(listing.url)

            if not provider:
                raise ValueError(f"No provider available for primary URL: {listing.url}")

            parse_result_primary: ParseResult = await provider.parse_html(listing.url, primary_html)
            primary_text = parse_result_primary.extracted_text

            source_url = parse_result_primary.original_link

            redirect_parsed_text = None
            redirect_url = str(source_url) if source_url else None
            redirect_html: Optional[str] = None

            if redirect_url and redirect_url != listing.url:
                listing.url_redirect = redirect_url
                try:

                    logger.info(f"[{listing_id}] Processing source URL: {redirect_url}")
                    redirect_html = await fetch_html_content(redirect_url)
                    source_provider: Optional[BaseProvider] = self.provider_registry.get_provider_for_content(
                        redirect_url)

                    if source_provider:
                        redirect_parse_result = await source_provider.parse_html(redirect_url, redirect_html)
                        redirect_parsed_text = redirect_parse_result.extracted_text if redirect_parse_result else None

                    else:
                        logger.warning(f"[{listing_id}] No provider found for source URL: {redirect_url}")
                        listing.error_message = "No provider found for source URL"
                except Exception as source_error:
                    logger.warning(f"[{listing_id}] Failed to process source URL {source_url}: {source_error}",
                                   exc_info=False)
                    listing.error_message = f"Error fetching/parsing source: {source_error}"  # Store error info

            analysis_result = await self.ai_analyzer.analyze_multiple_texts(
                primary_text=primary_text,
                secondary_text=redirect_parsed_text
            )

            await self.save_successful_listing(analysis_result,
                                               listing,
                                               primary_html,
                                               primary_text,
                                               redirect_html,
                                               redirect_parsed_text,
                                               redirect_url)


        except Exception as e:
            logger.error(f"[{listing_id}] Error during analysis task: {e}", exc_info=True)
            listing: Listing = await self.listing_repository.find_by_id(listing_id)
            try:
                listing.status = AnalysisStatus.ERROR
                listing.error_message = str(e)
                await self.listing_repository.save(listing)
                logger.info(f"[{listing_id}] Saved listing with ERROR status.")
            except Exception as save_err:
                logger.critical(
                    f"[{listing_id}] CRITICAL: Failed to save ERROR status after analysis failure: {save_err}",
                    exc_info=True)

    async def save_successful_listing(self, analysis_result, listing, primary_html, primary_text, redirect_html,
                                      redirect_parsed_text, redirect_url):
        listing.status = AnalysisStatus.COMPLETED
        listing.analysis = analysis_result
        listing.html_url = primary_html
        listing.text_extracted = primary_text
        listing.html_url_redirect = redirect_html if redirect_html else None
        listing.text_extracted_redirect = redirect_parsed_text if redirect_parsed_text else None
        listing.url_redirect = redirect_url if redirect_url else None
        await self.listing_repository.save(listing)
        logger.info(f"[{listing.id}] Analysis task completed successfully.")

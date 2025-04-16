import logging
from typing import Dict, Any
from uuid import UUID

from src.app.lib.url_utils import normalize_url
from src.app.lib.url_validation import validate_listing_url
from src.app.lib.html_utils import fetch_html_content
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.analyze import AnalysisRequest, AnalysisStatus
from .ai_analyzer import AIAnalyzerService
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
        """
        Validate URL, normalize it, and create or get a listing in the database.
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
        """Process a listing by fetching HTML, parsing, and handling source URLs."""
        try:
            listing = await self.listing_repository.find_by_id(listing_id)
            if not listing:
                logger.error(f"Listing {listing_id} not found")
                return
                
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                status=AnalysisStatus.FETCHING_HTML
            )
            
            url = listing["url"]
            html_content = await fetch_html_content(url)
            
            provider = self.provider_registry.get_provider_for_content(url)
            if not provider:
                raise ValueError(f"No provider available for URL: {url}")
                
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                status=AnalysisStatus.PARSING_DATA,
                html_content_primary=html_content
            )
            
            parse_result = await provider.parse_html(url, html_content)
            
            source_url = parse_result.get("originalLink")
            source_content = None
            source_parse_result = None
            
            if source_url and source_url != url:
                logger.info(f"Found source URL: {source_url}")
                
                await self.listing_repository.update_listing(
                    listing_id=listing_id,
                    status=AnalysisStatus.FETCHING_HTML,
                    source_url=source_url
                )
                
                try:
                    source_content = await fetch_html_content(source_url)
                    source_provider = self.provider_registry.get_provider_for_content(source_url)
                    
                    if source_provider:
                        source_parse_result = await source_provider.parse_html(source_url, source_content)
                except Exception as source_error:
                    logger.warning(f"Error processing source URL: {source_error}")
            
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                status=AnalysisStatus.GENERATING_INSIGHTS,
                html_content_secondary=source_content
            )
            
            primary_text = parse_result.get("extractedText", "")
            secondary_text = source_parse_result.get("extractedText") if source_parse_result else None
            
            analysis_result = await self.ai_analyzer.analyze_multiple_texts(
                primary_text=primary_text,
                secondary_text=secondary_text
            )
            
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                analysis_result=analysis_result,
                status=AnalysisStatus.COMPLETED
            )

        except Exception as e:
            logger.error(f"[{listing_id}] Error during analysis: {e}", exc_info=True)
            await self.listing_repository.update_listing(
                listing_id=listing_id,
                status=AnalysisStatus.ERROR,
                error_message=str(e)
            )

import logging
import uuid
from typing import Optional, Dict, Any

import httpx

# Import provider related modules
from src.app.lib.providers.base_provider import HtmlParseResult
from src.app.lib.providers.provider_registry import get_provider_registry, ProviderRegistry
# Import necessary modules
from src.app.lib.url_utils import normalize_url
from src.app.schemas.analyze import AnalysisResultData
# Import the AI Analyzer Service
from .ai_analyzer import AIAnalyzerService
# Import Repository and Status Enum
from src.app.repositories.listing_repository import ListingRepository
from src.app.schemas.status import AnalysisStatus

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


async def _fetch_html_content(url: str) -> str:
    """Fetches HTML content from a URL with timeout and user-agent."""
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                logger.warning(f"Content-Type for {url} is not text/html: {content_type}")
            return response.text
        except httpx.RequestError as exc:
            logger.error(f"HTTP RequestError while fetching {url}: {exc}")
            raise ConnectionError(f"Failed to connect to {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP StatusError while fetching {url}: {exc.response.status_code}")
            raise ValueError(f"Failed to fetch {url}: Status {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error(f"Unexpected error fetching {url}: {exc}", exc_info=True)
            raise RuntimeError(f"Unexpected error fetching {url}") from exc


def _combine_texts(primary_result: HtmlParseResult, secondary_result: Optional[HtmlParseResult]) -> str:
    """Combines extracted text from primary and secondary sources for AI input."""
    primary_text = primary_result.get("extractedText", "")
    if not secondary_result or not secondary_result.get("extractedText"):
        return primary_text or ""  # Ensure empty string if primary is also empty

    secondary_text = secondary_result.get("extractedText", "")
    # Basic combination, could be refined based on provider knowledge
    # Ensure primary_text is not None before formatting
    primary_text_content = primary_text if primary_text else "N/A"
    secondary_text_content = secondary_text if secondary_text else "N/A"
    return f"PRIMARY SOURCE (e.g., Boligsiden):\n{primary_text_content}\n\n---\n\nSECONDARY SOURCE (e.g., Realtor Site):\n{secondary_text_content}"


async def prepare_analysis(url: str, repository: ListingRepository) -> uuid.UUID:
    """
    Checks if a listing exists for the given URL, creates one if not,
    and returns the listing ID. Re-queues if the existing status is an error state.
    """
    logger.info(f"Preparing analysis for URL: {url}")
    normalized_url = normalize_url(url)

    try:
        listing = await repository.create_or_get_listing(url, normalized_url)
        listing_id = listing['id']
        existing_status = AnalysisStatus(listing['status']) # Convert string status to Enum

        logger.info(f"Using listing ID: {listing_id}, Current Status: {existing_status.value}")

        # Re-queue if the listing is in a final error state
        if existing_status in [AnalysisStatus.ERROR, AnalysisStatus.TIMEOUT, AnalysisStatus.INVALID_URL, AnalysisStatus.CANCELLED]:
            logger.info(f"Re-queuing analysis for listing {listing_id} due to status: {existing_status.value}")
            await repository.update_status(listing_id, AnalysisStatus.QUEUED)
        elif existing_status == AnalysisStatus.COMPLETED:
            logger.info(f"Analysis for listing {listing_id} already completed. Not re-queuing.")
        elif existing_status != AnalysisStatus.PENDING and existing_status != AnalysisStatus.QUEUED:
             logger.info(f"Analysis for listing {listing_id} is already in progress (status: {existing_status.value}). Not re-queuing.")
        # If PENDING or QUEUED, no action needed here, the task runner will pick it up.

        return listing_id

    except Exception as e:
        logger.error(f"Error preparing analysis for {url}: {e}", exc_info=True)
        # Consider specific exception handling if needed
        raise Exception(f"Failed to prepare analysis for {url}: {e}") from e


async def start_analysis_task(listing_id: uuid.UUID, url: str, repository: ListingRepository):
    """
    The actual analysis logic that runs in the background.
    Fetches content, parses using providers, calls AI, updates DB status and results.
    """
    logger.info(f"Starting background analysis task for listing ID: {listing_id}, URL: {url}")
    html_content_primary: Optional[str] = None
    html_content_secondary: Optional[str] = None
    parse_result_primary: Optional[HtmlParseResult] = None
    parse_result_secondary: Optional[HtmlParseResult] = None
    provider_registry: ProviderRegistry = get_provider_registry()
    ai_analyzer: Optional[AIAnalyzerService] = None # Initialize AI Analyzer

    try:
        # Instantiate AI Analyzer safely
        try:
            ai_analyzer = AIAnalyzerService()
        except (ImportError, ValueError) as ai_init_error:
            logger.error(f"[{listing_id}] Failed to initialize AIAnalyzerService: {ai_init_error}")
            raise RuntimeError(f"AI Service configuration error: {ai_init_error}") from ai_init_error

        # 1. Fetch primary HTML content
        await repository.update_status(listing_id, AnalysisStatus.FETCHING_HTML)
        logger.info(f"[{listing_id}] Fetching primary HTML from: {url}")
        html_content_primary = await _fetch_html_content(url)
        logger.info(f"[{listing_id}] Fetched primary HTML (length: {len(html_content_primary)})")

        # 2. Parse primary HTML using ProviderRegistry
        await repository.update_status(listing_id, AnalysisStatus.PARSING_DATA)
        logger.info(f"[{listing_id}] Finding provider and parsing primary HTML...")
        provider = provider_registry.get_provider_for_content(url, html_content_primary)
        parse_result_primary = await provider.parse_html(url, html_content_primary)
        logger.info(f"[{listing_id}] Parsed primary HTML using provider: {provider.name}")

        if not parse_result_primary or parse_result_primary.get("error"):
            error_detail = parse_result_primary.get("error",
                                                    "Unknown parsing error") if parse_result_primary else "Provider returned None"
            raise ValueError(f"Primary parsing failed: {error_detail}")

        # 3. Fetch and Parse secondary HTML if originalLink exists
        original_link = parse_result_primary.get("originalLink")
        original_link = parse_result_primary.get("originalLink")
        if original_link and original_link != url:
            # Status update before fetching secondary source (aligns with TS)
            await repository.update_status(listing_id, AnalysisStatus.PREPARING_ANALYSIS)
            logger.info(f"[{listing_id}] Fetching secondary HTML from redirect: {original_link}")
            try:
                html_content_secondary = await _fetch_html_content(original_link)
                logger.info(f"[{listing_id}] Fetched secondary HTML (length: {len(html_content_secondary)})")

                # Status update before parsing secondary source (can keep PREPARING_ANALYSIS or add another like PARSING_SECONDARY)
                # Let's stick to PREPARING_ANALYSIS for now as per TS logic before AI call.
                logger.info(f"[{listing_id}] Finding provider and parsing secondary HTML...")
                # Status update before parsing secondary source (can keep PREPARING_ANALYSIS or add another like PARSING_SECONDARY)
                # Let's stick to PREPARING_ANALYSIS for now as per TS logic before AI call.
                logger.info(f"[{listing_id}] Finding provider and parsing secondary HTML...")
                try:
                    source_provider = provider_registry.get_provider_for_content(original_link, html_content_secondary)
                    parse_result_secondary = await source_provider.parse_html(original_link, html_content_secondary)
                    logger.info(f"[{listing_id}] Parsed secondary HTML using provider: {source_provider.name}")
                    if parse_result_secondary and parse_result_secondary.get("error"):
                        logger.warning(
                            f"[{listing_id}] Secondary parsing resulted in error: {parse_result_secondary['error']}")
                        parse_result_secondary = None # Treat parsing error as no secondary data
                except ValueError as e:
                    logger.warning(
                        f"[{listing_id}] Could not find provider for secondary URL {original_link}: {e}. Proceeding without secondary data.")
                    parse_result_secondary = None
                except Exception as e: # Catch other potential parsing errors
                    logger.error(f"[{listing_id}] Error parsing secondary HTML from {original_link}: {e}", exc_info=True)
                    parse_result_secondary = None

            except (ConnectionError, ValueError, RuntimeError, httpx.TimeoutException) as fetch_exc:
                 # Handle fetch errors for the secondary URL gracefully
                 logger.warning(f"[{listing_id}] Failed to fetch or process secondary URL {original_link}: {fetch_exc}. Proceeding without secondary data.")
                 html_content_secondary = None
                 parse_result_secondary = None
            except Exception as e: # Catch unexpected errors during secondary fetch/parse
                 logger.error(f"[{listing_id}] Unexpected error processing secondary URL {original_link}: {e}", exc_info=True)
                 html_content_secondary = None
                 parse_result_secondary = None
        else: # Corresponds to 'if original_link and original_link != url:'
            logger.info(f"[{listing_id}] No distinct original link found or same as primary URL.")

        # Update metadata in DB (moved after secondary processing)
        metadata_to_update = {
            "property_image_url": parse_result_primary.get("property_image_url"),
            "url_redirect": original_link if original_link and original_link != url else None,
            "text_extracted": parse_result_primary.get("extractedText"),
            "text_extracted_redirect": parse_result_secondary.get("extractedText") if parse_result_secondary else None,
            # Consider adding html_content if needed by repo, but keep it concise for now
        }
        await repository.update_listing_metadata(listing_id, metadata_to_update)


        # 4. Prepare text and call AI Analyzer
        await repository.update_status(listing_id, AnalysisStatus.GENERATING_INSIGHTS)
        logger.info(f"[{listing_id}] Preparing text and starting AI analysis...")
        combined_text = _combine_texts(parse_result_primary, parse_result_secondary)

        if not combined_text or combined_text.strip() == "":
            # If no text could be extracted at all, mark as error
            logger.error(f"[{listing_id}] No text content extracted from primary or secondary sources.")
            raise ValueError("No text content extracted for AI analysis.")

        # Call the actual AI analyzer service
        analysis_result_dict = await ai_analyzer.analyze_text(combined_text)
        # Validate the result structure (optional but recommended)
        try:
            analysis_result = AnalysisResultData(**analysis_result_dict)
            logger.info(f"[{listing_id}] AI analysis completed and validated.")
        except Exception as validation_error:  # Catch Pydantic validation error
            logger.error(f"[{listing_id}] AI response failed validation: {validation_error}", exc_info=True)
            logger.error(f"[{listing_id}] Raw AI response: {analysis_result_dict}")
            raise ValueError(f"AI response format error: {validation_error}") from validation_error

        # 5. Save result and finalize
        await repository.update_status(listing_id, AnalysisStatus.FINALIZING)
        await repository.save_analysis_result(listing_id, analysis_result.model_dump()) # Save validated data
        await repository.update_status(listing_id, AnalysisStatus.COMPLETED)
        logger.info(f"Analysis task completed successfully for listing ID: {listing_id}")

    except httpx.TimeoutException as timeout_exc:
        logger.error(f"[{listing_id}] Timeout during analysis task: {timeout_exc}", exc_info=True)
        await repository.set_error_status(listing_id, AnalysisStatus.TIMEOUT, f"Timeout: {timeout_exc}")
    except (ConnectionError, ValueError, RuntimeError) as processing_exc: # Catch known fetch/parse/AI errors
        logger.error(f"[{listing_id}] Error during analysis task: {processing_exc}", exc_info=True)
        # Determine specific error status if possible (e.g., INVALID_URL)
        error_status = AnalysisStatus.ERROR # Default
        if "No suitable provider found" in str(processing_exc):
             error_status = AnalysisStatus.INVALID_URL # Or a more specific provider error status
        elif "Failed to fetch" in str(processing_exc) or "Failed to connect" in str(processing_exc):
             error_status = AnalysisStatus.INVALID_URL # Or potentially TIMEOUT if it was connection timeout related
        # Add more specific checks if needed
        await repository.set_error_status(listing_id, error_status, f"{type(processing_exc).__name__}: {processing_exc}")
    except Exception as e:
        logger.error(f"[{listing_id}] Unexpected error during analysis task for listing ID: {listing_id}", exc_info=True)
        await repository.set_error_status(listing_id, AnalysisStatus.ERROR, f"Unexpected {type(e).__name__}: {e}")


async def get_analysis_status_and_result(listing_id: uuid.UUID, repository: ListingRepository) -> Dict[str, Any]:
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
    except ValueError as ve: # Catch not found specifically
        logger.warning(f"Value error fetching status for {listing_id}: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"Database error fetching status for listing {listing_id}: {e}", exc_info=True)
        raise Exception(f"Database error fetching status: {e}") from e



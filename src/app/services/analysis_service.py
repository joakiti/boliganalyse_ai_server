import datetime
import logging
import uuid
from typing import Optional, Dict, Any

import httpx
from postgrest import APIResponse
from supabase import AsyncClient

from src.app.lib.providers.base_provider import HtmlParseResult
# Import provider related modules
from src.app.lib.providers.provider_registry import get_provider_registry, ProviderRegistry
# Import necessary modules
from src.app.lib.supabase_client import get_supabase_admin_client
from src.app.lib.url_utils import normalize_url
from src.app.schemas.analyze import AnalysisResultData
# Import the AI Analyzer Service
from .ai_analyzer import AIAnalyzerService

logger = logging.getLogger(__name__)

LISTINGS_TABLE = "apartment_listings"
DB_SCHEMA = "private"
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


async def prepare_analysis(url: str) -> uuid.UUID:
    """Checks if listing exists, creates/updates DB entry, returns listing ID."""
    logger.info(f"Preparing analysis for URL: {url}")
    normalized_url = normalize_url(url)
    supabase: AsyncClient = await get_supabase_admin_client()

    insert_data = {
        "url": url,
        "normalized_url": normalized_url,
        "status": "queued",
    }

    response: APIResponse = await supabase.schema(DB_SCHEMA).from_(LISTINGS_TABLE).insert(insert_data).execute()

    if response.data:
        listing_id = response.data.id
        logger.info(f"Created new listing entry with ID: {listing_id}")
        return uuid.UUID(listing_id)

    elif response.error and response.error.code == '23505':  # Unique constraint violation
        logger.warning(f"Listing with normalized URL {normalized_url} already exists. Checking status.")
        select_response: APIResponse = await supabase.from_(LISTINGS_TABLE, schema=DB_SCHEMA) \
            .select("id, status") \
            .eq("normalized_url", normalized_url) \
            .single()

        if select_response.error:
            logger.error(f"Error fetching existing listing for {normalized_url}", exc_info=select_response.error)
            raise Exception(f"Failed to fetch existing listing: {select_response.error.message}")

        if not select_response.data:
            logger.error(f"Conflict error but could not fetch existing listing for {normalized_url}")
            raise Exception("Database inconsistency detected.")

        existing_id_str = select_response.data['id']
        existing_status = select_response.data['status']
        existing_id = uuid.UUID(existing_id_str)
        logger.info(f"Existing listing ID: {existing_id}, Status: {existing_status}")

        if existing_status in ["error", "timeout", "invalid_url"]:
            logger.info(f"Re-queuing analysis for listing {existing_id} due to status: {existing_status}")
            await update_status(existing_id, "queued")
            return existing_id
        elif existing_status == "completed":
            logger.info(f"Analysis for listing {existing_id} already completed. Not re-queuing.")
            return existing_id
        else:
            logger.info(
                f"Analysis for listing {existing_id} is already in progress (status: {existing_status}). Not re-queuing.")
            return existing_id

    elif response.error:
        logger.error(f"Error inserting listing for {url}", exc_info=response.error)
        raise Exception(f"Failed to create listing entry: {response.error.message}")
    else:
        logger.error(f"Unexpected response during listing insert for {url}")
        raise Exception("Failed to create or find listing entry.")


async def start_analysis_task(listing_id: uuid.UUID, url: str):
    """
    The actual analysis logic that runs in the background.
    Fetches content, parses using providers, calls AI, updates DB.
    """
    logger.info(f"Starting background analysis task for listing ID: {listing_id}, URL: {url}")
    html_content_primary: Optional[str] = None
    html_content_secondary: Optional[str] = None
    parse_result_primary: Optional[HtmlParseResult] = None
    parse_result_secondary: Optional[HtmlParseResult] = None
    provider_registry: ProviderRegistry = get_provider_registry()
    ai_analyzer: Optional[AIAnalyzerService] = None  # Initialize AI Analyzer

    try:
        # Instantiate AI Analyzer safely
        try:
            ai_analyzer = AIAnalyzerService()
        except (ImportError, ValueError) as ai_init_error:
            logger.error(f"[{listing_id}] Failed to initialize AIAnalyzerService: {ai_init_error}")
            raise RuntimeError(f"AI Service configuration error: {ai_init_error}") from ai_init_error

        # 1. Fetch primary HTML content
        await update_status(listing_id, "fetching_html")
        logger.info(f"[{listing_id}] Fetching primary HTML from: {url}")
        html_content_primary = await _fetch_html_content(url)
        logger.info(f"[{listing_id}] Fetched primary HTML (length: {len(html_content_primary)})")

        # 2. Parse primary HTML using ProviderRegistry
        await update_status(listing_id, "parsing_data")
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
        if original_link and original_link != url:
            await update_status(listing_id, "fetching_redirect_html")
            logger.info(f"[{listing_id}] Fetching secondary HTML from redirect: {original_link}")
            html_content_secondary = await _fetch_html_content(original_link)
            logger.info(f"[{listing_id}] Fetched secondary HTML (length: {len(html_content_secondary)})")

            await update_status(listing_id, "parsing_redirect_data")
            logger.info(f"[{listing_id}] Finding provider and parsing secondary HTML...")
            try:
                source_provider = provider_registry.get_provider_for_content(original_link, html_content_secondary)
                parse_result_secondary = await source_provider.parse_html(original_link, html_content_secondary)
                logger.info(f"[{listing_id}] Parsed secondary HTML using provider: {source_provider.name}")
                if parse_result_secondary and parse_result_secondary.get("error"):
                    logger.warning(
                        f"[{listing_id}] Secondary parsing resulted in error: {parse_result_secondary['error']}")
                    parse_result_secondary = None
            except ValueError as e:
                logger.warning(
                    f"[{listing_id}] Could not find provider for secondary URL {original_link}: {e}. Proceeding without secondary data.")
                parse_result_secondary = None
        else:
            logger.info(f"[{listing_id}] No distinct original link found or same as primary URL.")

        # Update metadata in DB
        metadata_to_update = {
            "property_image_url": parse_result_primary.get("property_image_url"),
            "url_redirect": original_link if original_link and original_link != url else None,
            "text_extracted": parse_result_primary.get("extractedText"),
            "text_extracted_redirect": parse_result_secondary.get("extractedText") if parse_result_secondary else None,
        }
        await update_listing_metadata(listing_id, metadata_to_update)

        # 4. Prepare text and call AI Analyzer
        await update_status(listing_id, "generating_insights")
        logger.info(f"[{listing_id}] Preparing text and starting AI analysis...")
        combined_text = _combine_texts(parse_result_primary, parse_result_secondary)

        if not combined_text or combined_text.strip() == "":
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
        await update_status(listing_id, "finalizing")
        await save_result(listing_id, analysis_result.model_dump())  # Save validated data
        await update_status(listing_id, "completed")
        logger.info(f"Analysis task completed successfully for listing ID: {listing_id}")

    except Exception as e:
        logger.error(f"Analysis task failed for listing ID: {listing_id}", exc_info=True)
        await update_status(listing_id, "error", f"{type(e).__name__}: {e}")  # Log exception type and message


async def get_analysis_status_and_result(listing_id: uuid.UUID) -> Dict[str, Any]:
    """Fetches the current status, analysis result, and other relevant data for a listing."""
    # (Implementation remains the same)
    logger.info(f"Fetching status and data for listing ID: {listing_id}")
    supabase: AsyncClient = await get_supabase_admin_client()

    response: APIResponse = await supabase.from_(LISTINGS_TABLE, schema=DB_SCHEMA) \
        .select(
        "id, status, analysis, error_message, url, realtor, created_at, updated_at, property_image_url, url_redirect") \
        .eq("id", str(listing_id)) \
        .single()

    if response.error:
        logger.error(f"Error fetching status for listing {listing_id}", exc_info=response.error)
        if response.error.code == 'PGRST116':
            raise ValueError(f"Listing with ID {listing_id} not found.")
        raise Exception(f"Database error fetching status: {response.error.message}")

    if not response.data:
        raise ValueError(f"Listing with ID {listing_id} not found.")

    return response.data


# --- Helper functions for DB interaction ---
# (update_status, save_result, update_listing_metadata remain the same)
async def update_status(listing_id: uuid.UUID, status: str, error_message: Optional[str] = None):
    """Updates the status and optionally error message for a listing."""
    logger.debug(
        f"Updating status for {listing_id} to {status}" + (f" (Error: {error_message})" if error_message else ""))
    supabase: AsyncClient = await get_supabase_admin_client()
    update_data: Dict[str, Any] = {
        "status": status,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    if error_message is not None:
        update_data["error_message"] = error_message[:1000]  # Truncate
    elif status not in ["error", "timeout", "invalid_url"]:  # Clear error on non-error status
        update_data["error_message"] = None

    response: APIResponse = await supabase.from_(LISTINGS_TABLE, schema=DB_SCHEMA) \
        .update(update_data) \
        .eq("id", str(listing_id)) \
        .execute()  # Add execute() to run the query

    if response.error:
        logger.error(f"Failed to update status for {listing_id} to {status}", exc_info=response.error)


async def save_result(listing_id: uuid.UUID, result: Dict[str, Any]):
    """Saves the analysis result JSON to the database."""
    logger.debug(f"Saving result for {listing_id}")
    supabase: AsyncClient = await get_supabase_admin_client()
    response: APIResponse = await supabase.from_(LISTINGS_TABLE, schema=DB_SCHEMA) \
        .update({
        "analysis": result,  # Store the validated Pydantic model dict
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }) \
        .eq("id", str(listing_id)) \
        .execute()  # Add execute() to run the query

    if response.error:
        logger.error(f"Failed to save analysis result for {listing_id}", exc_info=response.error)


async def update_listing_metadata(listing_id: uuid.UUID, metadata: Dict[str, Any]):
    """Updates specific metadata fields for a listing, ignoring None values."""
    update_data = {k: v for k, v in metadata.items() if v is not None}

    if not update_data:
        logger.debug(f"No metadata to update for listing {listing_id}")
        return

    update_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.debug(f"Updating metadata for {listing_id}: {list(update_data.keys())}")
    supabase: AsyncClient = await get_supabase_admin_client()
    response: APIResponse = await supabase.from_(LISTINGS_TABLE, schema=DB_SCHEMA) \
        .update(update_data) \
        .eq("id", str(listing_id)) \
        .execute()  # Add execute() to run the query

    if response.error:
        logger.error(f"Failed to update metadata for {listing_id}", exc_info=response.error)

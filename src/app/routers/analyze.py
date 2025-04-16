from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
import logging
import uuid # Import uuid

from src.app.schemas.analyze import AnalysisRequest, AnalysisSubmitResponse, AnalysisStatusResponse
from src.app.services.analysis_service import prepare_analysis, start_analysis_task, get_analysis_status_and_result
from src.app.repositories.listing_repository import ListingRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# Create a repository instance
repository = ListingRepository()

@router.post(
    "/analyze",
    response_model=AnalysisSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED, # Use 202 Accepted for async tasks
    summary="Submit Listing URL for Analysis",
    description="Accepts a URL for a real estate listing, creates a database entry (if new), "
                "and queues the analysis to run in the background."
)
async def submit_analysis(
    request_data: AnalysisRequest,
    background_tasks: BackgroundTasks,
    # current_user: dict = Depends(get_current_user) # Uncomment to protect endpoint
):
    """
    Endpoint to submit a new URL for analysis.

    - Validates the request data.
    - Calls the service layer to prepare the analysis (check/create DB entry).
    - Adds the main analysis task to run in the background.
    - Returns immediately with the listing ID.
    """
    logger.info(f"Received analysis submission request for URL: {request_data.url}")
    try:
        # Prepare analysis: checks DB, creates/updates entry, returns ID
        listing_id = await prepare_analysis(request_data.url, repository)

        # Add the heavy lifting (fetching, parsing, AI call, DB updates) to background tasks
        # Pass listing_id (UUID) and original URL
        background_tasks.add_task(start_analysis_task, listing_id, request_data.url, repository)
        logger.info(f"Analysis task added to background queue for listing ID: {listing_id}")

        return AnalysisSubmitResponse(
            message="Analysis accepted and queued for processing.",
            listing_id=listing_id
        )
    except Exception as e:
        logger.error(f"Error submitting analysis for URL {request_data.url}: {e}", exc_info=True)
        # Provide a more generic error to the client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate analysis process. Please try again later."
        )

@router.get(
    "/analyze/{listing_id}",
    response_model=AnalysisStatusResponse,
    summary="Get Analysis Status and Result",
    description="Retrieves the current status and, if available, the analysis results for a given listing ID."
)
async def get_analysis_result(
    listing_id: uuid.UUID, # Use UUID type for path parameter validation
    # current_user: dict = Depends(get_current_user) # Uncomment to protect endpoint
):
    """
    Endpoint to check the status and retrieve the result of an analysis.

    - Fetches the status, analysis result (JSON), and error message from the database.
    - Returns the data in a structured format.
    """
    logger.info(f"Received request for analysis status/result for ID: {listing_id}")
    try:
        status_str, result_json, error_msg = await get_analysis_status_and_result(listing_id)

        # Fetch additional details like URL, realtor, timestamps from DB if needed
        # For now, we only return what get_analysis_status_and_result provides

        return AnalysisStatusResponse(
            listing_id=listing_id,
            status=status_str,
            analysis=result_json, # Pydantic will validate this against AnalysisResultData
            error_message=error_msg
            # Add created_at, updated_at, url, realtor fields here if fetched
        )
    except ValueError as e:
        # Handle case where listing ID is not found (raised by service)
        logger.warning(f"Listing ID not found: {listing_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) # Pass the error message from the service
        )
    except Exception as e:
        logger.error(f"Error retrieving analysis status for ID {listing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis status. Please try again later."
        )

# Potential future endpoints:
# - GET /analyze/ : List recent analyses (with pagination)
# - DELETE /analyze/{listing_id} : Cancel or delete an analysis
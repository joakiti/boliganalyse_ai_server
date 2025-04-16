from fastapi import APIRouter, BackgroundTasks, HTTPException
from uuid import UUID

from src.app.schemas.analyze import AnalysisRequest, AnalysisSubmitResponse, AnalysisStatusResponse
from src.app.services.analysis_service import AnalysisService

router = APIRouter()
analysis_service = AnalysisService()

@router.post("/analyze", response_model=AnalysisSubmitResponse)
async def submit_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks) -> AnalysisSubmitResponse:
    """
    Submit a new URL for analysis.
    
    Args:
        request: The analysis request containing the URL
        background_tasks: FastAPI background tasks
        
    Returns:
        AnalysisResponse with listing ID and status
        
    Raises:
        HTTPException: If the request is invalid or processing fails
    """
    try:
        result = await analysis_service.submit_analysis(request)
        return AnalysisSubmitResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analyze/{listing_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(listing_id: UUID) -> AnalysisStatusResponse:
    """
    Get the status of an analysis.
    
    Args:
        listing_id: The ID of the listing to check
        
    Returns:
        AnalysisResponse with status and result if available
        
    Raises:
        HTTPException: If the listing is not found or processing fails
    """
    try:
        result = await analysis_service.get_analysis_status(listing_id)
        return AnalysisStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Potential future endpoints:
# - GET /analyze/ : List recent analyses (with pagination)
# - DELETE /analyze/{listing_id} : Cancel or delete an analysis
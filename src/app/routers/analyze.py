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
        result = await analysis_service.submit_analysis(request, background_tasks)
        return AnalysisSubmitResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
from pydantic import BaseModel, HttpUrl, Field, validator
from typing import Optional, List, Dict, Any
import uuid
import datetime # Import datetime
from uuid import UUID

from src.app.schemas.status import AnalysisStatus

# --- Request Schemas ---

class AnalysisRequest(BaseModel):
    """Request model for submitting a URL for analysis."""
    url: HttpUrl

    @validator('url')
    def url_must_be_string(cls, v):
        # Ensure the HttpUrl is converted back to a string if needed downstream
        return str(v)

# --- Response Schemas ---

class Recommendation(BaseModel):
    promptTitle: str = Field(..., description="Title for the recommendation, e.g., 'Spørg mægler'")
    prompt: str = Field(..., description="Specific question or action recommended")

class RiskItem(BaseModel):
    category: str = Field(..., description="Category of the risk (e.g., Energi, Tilstand)")
    title: str = Field(..., description="Short title of the risk")
    details: str = Field(..., description="Detailed explanation of the risk")
    excerpt: str = Field(..., description="Relevant text excerpt or justification")
    recommendations: List[Recommendation] = Field(..., description="List of recommendations")

class HighlightItem(BaseModel):
    icon: str = Field(..., description="Icon name representing the highlight")
    title: str = Field(..., description="Short title of the highlight")
    details: str = Field(..., description="Detailed explanation of the highlight")

class PropertyDetails(BaseModel):
    # Using Optional[str] for flexibility, validation can be added if needed
    address: Optional[str] = None
    price: Optional[str] = None
    udbetaling: Optional[str] = None
    pricePerM2: Optional[str] = None
    size: Optional[str] = None
    værelser: Optional[str] = None
    floor: Optional[str] = None
    boligType: Optional[str] = None
    ejerform: Optional[str] = None
    energiMaerke: Optional[str] = None
    byggeaar: Optional[str] = None
    renoveringsaar: Optional[str] = None
    maanedligeUdgift: Optional[str] = None

class AnalysisResultData(BaseModel):
    # This structure mirrors the expected JSON output from the AI analysis
    summary: Optional[str] = None
    property: Optional[PropertyDetails] = None
    risks: Optional[List[RiskItem]] = None
    highlights: Optional[List[HighlightItem]] = None

class AnalysisSubmitResponse(BaseModel):
    message: str
    status: AnalysisStatus
    listing_id: uuid.UUID # Use UUID type for clarity

# Use this for the GET endpoint to return status and potentially the full result
class AnalysisStatusResponse(BaseModel):
    listing_id: UUID
    status: AnalysisStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime.datetime] = None # Use datetime
    updated_at: Optional[datetime.datetime] = None # Use datetime
    url: Optional[HttpUrl] = None # Include the original URL for context
    realtor: Optional[str] = None # Add realtor if available

    @validator('url', pre=True, always=True)
    def url_to_string(cls, v):
        # Ensure HttpUrl is converted to string for response if needed
        return str(v) if v else None
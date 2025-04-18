from enum import Enum
from typing import Final, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from src.app.schemas.status import AnalysisStatus


class DatabaseSchema(str, Enum):
    """Database schema names."""
    PRIVATE = "private"
    PUBLIC = "public"


class TableName(str, Enum):
    """Database table names."""
    APARTMENT_LISTINGS = "apartment_listings"


# Schema and table configuration
SCHEMA_CONFIG: Final[dict[str, str]] = {
    "schema": DatabaseSchema.PRIVATE,
    "apartment_listings": TableName.APARTMENT_LISTINGS,
}

# Maps from private.apartment_listings
class Listing(BaseModel):
    """
    Entity representing an apartment listing in the database.
    Matches the exact field names used in the database.
    """
    id: Optional[UUID] = None
    url: str
    normalized_url: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    url_redirect: Optional[str] = None
    property_image_url: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Content fields
    html_url: Optional[str] = None
    html_url_redirect: Optional[str] = None
    text_extracted: Optional[str] = None
    text_extracted_redirect: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        
    def to_db_dict(self) -> Dict[str, Any]:
        """
        Convert the entity to a dictionary for database operations.
        Converts status enum to string value.
        
        Returns:
            Dictionary with database field names and values
        """
        db_dict = self.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        
        # Convert enum to string
        if "status" in db_dict and isinstance(db_dict["status"], AnalysisStatus):
            db_dict["status"] = db_dict["status"].value
            
        return db_dict
    
    @classmethod
    def from_db_dict(cls, db_dict: Dict[str, Any]) -> 'Listing':
        """
        Create a Listing entity from a database dictionary.
        
        Args:
            db_dict: Dictionary from database
            
        Returns:
            Listing entity
        """
        result_dict = db_dict.copy()
        
        # Convert status string to enum
        if "status" in result_dict and isinstance(result_dict["status"], str):
            try:
                result_dict["status"] = AnalysisStatus(result_dict["status"])
            except ValueError:
                # If status is not valid enum value, use ERROR
                result_dict["status"] = AnalysisStatus.ERROR
                
        return cls(**result_dict)
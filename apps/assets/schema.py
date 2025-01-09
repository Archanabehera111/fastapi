from pydantic import BaseModel
from typing import Dict, List, Optional, Union, Any

class Filters(BaseModel):
    status: Optional[List[str]] = None  # Example: ["Installed"]

class SearchRequest(BaseModel):
    page: int = 1  # Default: 1
    size: int = 10  # Default: 10
    filters: Optional[Filters] = None  # Filters object (optional)

class SaveFiltersRequest(BaseModel):
    userId: Union[int, str]
    name: str
    filters: Dict[str, str]
    fields: List[str]

class GetFiltersByUserIdRequest(BaseModel):
    userId: Union[int, str]

class UpdateAssetRequest(BaseModel):
    # Example fields; replace these with actual fields from the assets table
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    # Add any other fields you expect to update in the asset

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Asset Name",
                "description": "Updated description of the asset.",
                "status": "Active",
                "category": "Electronics",
                "price": 299.99
            }
        }
        
class UpdateFilterRequest(BaseModel):
    id: str  # UUID or string format, as the 'id' is a string (UUID)
    name: str  # Name of the filter
    filters: Dict[str, List[str]]  # Filters as a dictionary, where values are lists of strings
    fields: List[Any]  # Fields as a list (can contain any data type)
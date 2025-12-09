from pydantic import BaseModel, Field
from datetime import datetime

# --- Pydantic Models for Requests/Responses ---

class VariantAllocation(BaseModel):
    """Defines a variant and its traffic weight."""
    name: str = Field(..., description="The unique name of the variant (e.g., 'red_button').")
    allocation_percent: float = Field(..., ge=0, le=100, description="Traffic percentage (e.g., 50.0).")

class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment via POST /experiments."""
    name: str
    description: str | None = None
    variants: list[VariantAllocation]

class ExperimentResponse(BaseModel):
    """Schema for the response after creating an experiment."""
    id: int
    name: str
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class ExperimentAssignmentResponse(BaseModel):
    """Schema returned by GET /assignment/{user_id}."""
    id: int
    experiment_id: int
    user_id: str
    variant_name: str
    assigned_at: datetime
    
    class Config:
        from_attributes = True
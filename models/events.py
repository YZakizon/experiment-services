from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime, timezone

class EventCreate(BaseModel):
    """Schema for recording a new event via POST /events."""
    user_id: str
    type: str = Field(..., description="Type of event (e.g., 'purchase', 'signup', 'click').")
    timestamp: datetime = Field(default=datetime.now(timezone.utc))
    properties: dict[str, Any] | None = Field(default_factory=dict, description="Flexible JSON for extra context.")

class EventResponse(BaseModel):
    """Schema for the response after recording an event."""
    id: int
    user_id: str
    type: str
    timestamp: datetime

    class Config:
        from_attributes = True
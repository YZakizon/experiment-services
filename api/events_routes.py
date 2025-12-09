from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session

from data.database import Event
from models.events import EventCreate, EventResponse
from models.results import ExperimentResultsSummary, VariantResult
from api.depends import CLIENT_AUTH, DB_DEPENDENCY, CACHE_CLIENT

import json

events_router = APIRouter(
    prefix="/events",
    tags=["events"],
    # You can add common dependencies here if needed for ALL experiment routes
    dependencies=[CLIENT_AUTH]
)

# POST /events (Events remain on the main app as a separate concern)
@events_router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def record_event_route(
    event_data: EventCreate,
    db: Session = DB_DEPENDENCY
):
    """Record a conversion event (click, purchase, signup) for a user."""
    
    # Convert Pydantic properties dict to JSON string for SQLite storage
    properties_json = json.dumps(event_data.properties) if event_data.properties else None
    
    db_event = Event(
        user_id=event_data.user_id,
        type=event_data.type,
        timestamp=event_data.timestamp,
        properties_json=properties_json
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event
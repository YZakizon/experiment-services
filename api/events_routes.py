from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Any
from datetime import datetime
from data.database import Event
from models.events import EventCreate, EventResponse
from api.depends import CLIENT_AUTH, DB_DEPENDENCY
from config import config # initialize logging

# Import the Celery task
from celery_tasks.event_tasks import insert_event_to_db
import json
import logging

logger = logging.getLogger(__name__)

events_router = APIRouter(
    prefix="/events",
    tags=["events"],
    # You can add common dependencies here if needed for ALL experiment routes
    dependencies=[CLIENT_AUTH]
)

# POST /events (Events remain on the main app as a separate concern)
@events_router.post("", status_code=status.HTTP_200_OK)
def record_event_route(
    event_data: EventCreate,
    db: Session = DB_DEPENDENCY
):
    """
    Record a conversion event (click, purchase, signup) for a user.
    This will go stright to a celery worker and return immediately with 200 OK
    The celery worker then will insert to events table.
    """
    
    # Convert Pydantic properties dict to JSON string for SQLite storage
    properties_json = json.dumps(event_data.properties) if event_data.properties else None
 
    # Prepare the dictionary payload for the task (must be JSON serializable)
    task_payload: dict[str, Any] = {
        'user_id': event_data.user_id,
        'type': event_data.type,
        # Celery requires simple serializable types (like string for datetime)
        'timestamp': event_data.timestamp.isoformat() if isinstance(event_data.timestamp, datetime) else event_data.timestamp,
        'properties_json': properties_json
    }
    
    # 2. Call the Celery task asynchronously
    # .delay() is non-blocking and immediately returns a successful response (200 OK)
    task = insert_event_to_db.delay(task_payload)
    logger.debug(f"insert_event_to_db task result:{task}")

    # 3. Return the task id
    return JSONResponse(content={"status": "success", "task_id": task.id}, status_code=status.HTTP_200_OK)
    

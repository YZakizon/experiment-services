from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

# Internal imports
from config import Config
from data.database import create_tables, get_db, Event, Experiment
from auth.security import get_current_client
from models.experiments import ExperimentCreate, ExperimentResponse, ExperimentAssignmentResponse
from models.events import EventCreate, EventResponse
from models.results import ExperimentResultsSummary, VariantResult
from services import assignment, results
from services.cache import get_cache_client, CacheClient, RealValkeyBackend

import contextlib
import json
import logging
import middleware

logger = logging.getLogger(__name__)


# 1. Define the Lifespan Context Manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the application.
    Code before 'yield' runs on startup.
    Code after 'yield' runs on shutdown.
    """
    # --- STARTUP LOGIC (Replaces @app.on_event("startup")) ---
    
    # Integrate the original on_startup logic here:
    try:
        logger.info("Application starting up: Initializing database connection pool and schema...")
        create_tables()
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        # Depending on criticality, you might raise the exception or shut down gracefully
    
    # The 'yield' pauses the function execution until the app shuts down
    yield
    
    # --- SHUTDOWN LOGIC (Replaces @app.on_event("shutdown")) ---
    logger.info("Application shutting down: Closing resources...")
    # Example: Close database connection pool, flush cache data, etc.

# --- FastAPI App Initialization ---
app = FastAPI(
    lifespan=lifespan,
    title="Simplified Experimentation API",
    version="1.0.0",
    description="A service for A/B testing: creation, assignment, events, and results."
)

# Add the middleware to the application
app.add_middleware(middleware.RequestIDMiddleware)

# @app.on_event("startup")
# def on_startup():
#     """Ensure the database tables are created when the app starts."""
#     create_tables()
#     logger.info("Database tables initialized successfully.")

# Dependencies
CLIENT_AUTH = Depends(get_current_client)
DB_DEPENDENCY = Depends(get_db)
CACHE_CLIENT = Depends(get_cache_client)

# --- API Endpoints ---

@app.get("/health")
def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

# POST /experiments
@app.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment_route(
    experiment_data: ExperimentCreate, 
    client_token: str = CLIENT_AUTH, 
    db: Session = DB_DEPENDENCY
):
    """Create a new experiment with variants and traffic allocation."""
    return assignment.create_new_experiment(db, experiment_data)

# GET /experiments/{id}/assignment/{user_id} (The Idempotent Logic)
@app.get("/experiments/{experiment_id}/assignment/{user_id}", response_model=ExperimentAssignmentResponse)
def get_user_assignment_route(
    experiment_id: int, 
    user_id: str,
    client_token: str = CLIENT_AUTH, 
    db: Session = DB_DEPENDENCY,
    cache: CacheClient = CACHE_CLIENT
):
    """Get user's variant assignment. Performs assignment if none exists."""
    return assignment.get_or_create_assignment(db, cache, experiment_id, user_id)

# POST /events
@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def record_event_route(
    event_data: EventCreate,
    client_token: str = CLIENT_AUTH, 
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

# GET /experiments/{id}/results
@app.get("/experiments/{experiment_id}/results", response_model=ExperimentResultsSummary)
def get_experiment_results_route(
    experiment_id: int, 
    client_token: str = CLIENT_AUTH, 
    db: Session = DB_DEPENDENCY,
    event_type: str = "purchase", # Default conversion type
    start_date: str | None = None 
):
    """
    Retrieve experiment performance summary, only counting events after assignment.
    """
    # CALL THE IMPLEMENTED SERVICE LOGIC
    return results.calculate_summary(
        db=db, 
        experiment_id=experiment_id, 
        event_type=event_type, 
        start_date=start_date
    )


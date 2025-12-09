from fastapi import FastAPI, Depends, status, HTTPException, APIRouter
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

# Import the modular router
from api.experiment_routes import experiment_router 
from api.events_routes import events_router

import contextlib
import logging
import middleware

logger = logging.getLogger(__name__)


# 1. Define the Lifespan Context Manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the application.
    """
    # --- STARTUP LOGIC ---
    try:
        logger.info("Application starting up: Initializing database connection pool and schema...")
        create_tables()
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
    
    yield
    
    # --- SHUTDOWN LOGIC ---
    logger.info("Application shutting down: Closing resources...")

# --- FastAPI App Initialization ---
app = FastAPI(
    lifespan=lifespan,
    title="Simplified Experimentation API",
    version="1.0.0",
    description="A service for A/B testing: creation, assignment, events, and results."
)

# Add the middleware to the application
app.add_middleware(middleware.RequestIDMiddleware)

# --- Include Modular Router (All /experiments/* endpoints) ---
app.include_router(experiment_router) # 
app.include_router(events_router)

# --- API Endpoints Remaining in Main App ---

@app.get("/health")
def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=status.HTTP_200_OK)


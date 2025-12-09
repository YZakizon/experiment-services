from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session

# Internal/Service Imports (These must match your actual project structure)
from models.experiments import ExperimentCreate, ExperimentResponse, ExperimentAssignmentResponse
from models.results import ExperimentResultsSummary, VariantResult
from services import assignment, results
from services.cache import CacheClient
from api.depends import CLIENT_AUTH, DB_DEPENDENCY, CACHE_CLIENT

# 1. Create the Experiment Router with the desired prefix and dependencies
experiment_router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
    dependencies=[CLIENT_AUTH], # CLIENT_AUTH is now applied to all routes in this router
)


# POST /experiments/ (Path is now just "/" because the prefix is set above)
@experiment_router.post(
    "", 
    response_model=ExperimentResponse, 
    status_code=status.HTTP_201_CREATED
)
def create_experiment_route(
    experiment_data: ExperimentCreate, 
    db: Session = DB_DEPENDENCY       # client_token is implicit from router dependencies
):
    """Create a new experiment with variants and traffic allocation."""
    return assignment.create_new_experiment(db, experiment_data)


# GET /experiments/{experiment_id}/assignment/{user_id} (The Idempotent Logic)
@experiment_router.get("/{experiment_id}/assignment/{user_id}", response_model=ExperimentAssignmentResponse)
def get_user_assignment_route(
    experiment_id: int, 
    user_id: str,
    db: Session = DB_DEPENDENCY,        # client_token is implicit from router dependencies
    cache: CacheClient = CACHE_CLIENT
):
    """Get user's variant assignment. Performs assignment if none exists."""
    return assignment.get_or_create_assignment(db, cache, experiment_id, user_id)


# GET /experiments/{id}/results
@experiment_router.get("/{experiment_id}/results", response_model=ExperimentResultsSummary)
def get_experiment_results_route(
    experiment_id: int, 
    db: Session = DB_DEPENDENCY,        # client_token is implicit from router dependencies
    event_type: str = "purchase", # Default conversion type
    start_date: str | None = None 
):
    """
    Retrieve experiment performance summary, only counting events after assignment.
    """
    return results.calculate_summary(
        db=db, 
        experiment_id=experiment_id, 
        event_type=event_type, 
        start_date=start_date
    )
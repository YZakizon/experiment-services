from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from data.database import Experiment, Variant, Assignment
from models.experiments import ExperimentCreate
from datetime import datetime, timezone
import random
import logging
from fastapi import HTTPException
from services.cache import CacheClient

logger = logging.getLogger(__name__)

# Define the maximum number of times to retry the transaction
MAX_RETRIES = 3

class Cache():
    def __init__(self):
        pass

# --- Experiment Creation ---
def create_new_experiment(db: Session, experiment_data: ExperimentCreate):
    """Creates a new experiment and its associated variants."""
    db_experiment = Experiment(name=experiment_data.name, description=experiment_data.description)
    db.add(db_experiment)
    db.flush() # Flush to get the experiment ID before committing

    for v in experiment_data.variants:
        db_variant = Variant(
            experiment_id=db_experiment.id,
            name=v.name,
            allocation_percent=v.allocation_percent
        )
        db.add(db_variant)
    
    db.commit()
    db.refresh(db_experiment)
    logger.info("create new experiment %s success with experiment id: %d", experiment_data.name, db_experiment.id)

    # TODO: set to cache
    return db_experiment

def get_existing_assignment(db: Session, cache: CacheClient, experiment_id: int, user_id: str):
    """ Get existing assignemtn from database """

    # TODO: Get from cache
    existing_assignment = cache.get_assignment(experiment_id, user_id)
    if not existing_assignment:
        existing_assignment = db.query(Assignment).filter(
                Assignment.user_id == user_id,
                Assignment.experiment_id == experiment_id
            ).first()
        
        if existing_assignment:
            cache.set_assignment(existing_assignment)
            logger.debug("get_existing_assignment %d cache miss", experiment_id)
    else:
        logger.debug("get_existing_assignment %d cache hit", experiment_id)
    
    return existing_assignment

def get_experiment(db: Session, cache: CacheClient, experiment_id: int,):
    """ Get experiment from database """

    # TODO Get from cache
    experiment = cache.get_experiment(experiment_id=experiment_id)
    if not experiment:
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).one_or_none()
        if experiment:
            cache.set_experiment(experiment=experiment)
            logger.debug("get_experiment %d cache miss", experiment_id)
    else:
        logger.debug("get_experiment %d cache hit", experiment_id)
        
    return experiment

def set_assignment(db: Session, cache: CacheClient, experiment_id: int, user_id: str, assignment: Assignment):
    """ Set assignment """

    db.add(assignment)
    db.commit() # This is where the database constraint check happens
    db.refresh(assignment)
    cache.set_assignment(assignment)

    # TODO: add to cache

# --- Idempotent Assignment ---
def get_or_create_assignment(db: Session, cache: CacheClient, experiment_id: int, user_id: str):
    """
    Retrieves an existing assignment or creates a new one if doesn't exist,
    safely handling concurrent requests using the Unique Constraint + Retry pattern.
    """
    
    # Retry loop handles concurrent inserts that fail the unique constraint
    for attempt in range(MAX_RETRIES):
        
        # 1. CHECK FOR EXISTING ASSIGNMENT 
        existing_assignment = get_existing_assignment(db=db, cache=cache, experiment_id=experiment_id, user_id=user_id)

        if existing_assignment:
            logger.info("Found persistent assignment for user %s on EID %d: %s", 
                        user_id, experiment_id, existing_assignment.variant_name)
            return existing_assignment

        # --- Assignment is NEW, proceed to create it ---
        
        try:
            # 2. PERFORM WEIGHTED RANDOM SELECTION
            # Fetch experiment details (variants and weights) - assumes Experiment model is available
            experiment = get_experiment(db=db, cache=cache, experiment_id=experiment_id)
            if not experiment or not experiment.variants:
                logger.info("Experiment ID %d not found or has no variants.", experiment_id)

                # this exception will be catched by out try/except, so it will need to re-raise
                raise HTTPException(status_code=404, detail=f"Experiment ID {experiment_id} not found or has no variants.")

                
            variant_names = [v.name for v in experiment.variants]
            weights = [v.allocation_percent for v in experiment.variants]
            assigned_variant_name = random.choices(variant_names, weights=weights, k=1)[0]
            
            # 3. ATTEMPT TO CREATE THE NEW ASSIGNMENT (THE WRITE)
            new_assignment = Assignment(
                user_id=user_id,
                experiment_id=experiment_id,
                variant_name=assigned_variant_name
            )
 
            set_assignment(db=db, cache=cache, experiment_id=experiment_id, user_id=user_id, assignment=new_assignment)
 
            logger.info("SUCCESS: User %s newly assigned to %s (EID %d) on attempt %d.", 
                           user_id, assigned_variant_name, experiment_id, attempt + 1)
            return new_assignment
            
        except IntegrityError:
            # 4. HANDLE THE RACE CONDITION (The Retry Mechanism)
            # IntegrityError is raised if a concurrent transaction beat us to the INSERT.
            db.rollback() # Rollback the failed INSERT to clear the session
            
            logger.warning("RACE DETECTED: IntegrityError on user %s (EID %d). Retrying (Attempt %d/%d)...",
                           user_id, experiment_id, attempt + 2, MAX_RETRIES)
                           
            # The loop immediately repeats, and on the next pass, the initial READ 
            # (Step 1) will now find the assignment created by the competing transaction.
        
        except HTTPException as e:
            # reraise this exception
            raise e
        
        except Exception as e:
            db.rollback()
            logger.exception("An unexpected error occurred during assignment for user %s.", user_id)
            raise HTTPException(status_code=400, detail=f"Experiment ID {experiment_id} unable to create assignment.")
            
    # If all retries fail, something is seriously wrong
    logger.warning("Failed to get or create assignment for user %s after %d attempts.", user_id, MAX_RETRIES)
    raise HTTPException(status_code=400, detail=f"Experiment ID {experiment_id} unable to create assignment.")
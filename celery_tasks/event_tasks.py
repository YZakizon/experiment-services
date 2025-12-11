from celery_config import celery_app
from data.database import Event, SessionLocal # Assuming SessionLocal is available to create isolated sessions
from typing import Any
from datetime import datetime
from config import config # initialize logging
import logging

logger = logging.getLogger(__name__)

# NOTE: This function simulates getting a fresh, isolated DB session 
# (You might need to implement SessionLocal in data/database.py)
def get_db_session():
    """Provides a fresh database session for asynchronous task execution."""
    try:
        db = SessionLocal() 
        return db
    except Exception as e:
        logger.error(f"Failed to create database session in Celery task: {e}")
        return None

# ignore result flag in celery as we don't need the result and reduced storage bloat
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, ignore_result_flag=True)
def insert_event_to_db(self, event_data_dict: dict[str, Any]):
    """
    Asynchronously inserts a recorded event into the database.
    This function must handle its own database session.
    Right now we're using postgres for simplicity, as it grows bigger this 
    needs to migrate to Clickhouse eventually for high performance events collecting and analysis
    """
    db = None
    db_event = None
    try:
        db = get_db_session()
        if not db:
            # Raise an exception to potentially trigger Celery retry
            raise ConnectionError("Could not establish database session.")
            
        # Create the ORM object from the dictionary data
        db_event = Event(
            user_id=event_data_dict['user_id'],
            type=event_data_dict['type'],
            timestamp=datetime.fromisoformat(event_data_dict['timestamp']),
            properties_json=event_data_dict['properties_json']
        )
        
        db.add(db_event)
        db.commit()
        # No refresh needed as the task doesn't need the resulting object
        
        logger.info(f"Task {self.name}[{self.request.id}]. Successfully inserted event for user {db_event.user_id} of type {db_event.type}.")
    except ConnectionError as exc:
        logger.error("Database connection failed in Celery task. Retrying...")
        # Retry the task if the connection failed
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(f"Failed to insert event to DB: {exc}. DB event: {db_event}")
        raise  # re-raise so Celery marks FAILURE and we can debug it
        
    finally:
        if db:
            db.close()
    
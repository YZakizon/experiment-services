from sqlalchemy.orm import Session
from sqlalchemy import func, select, literal
from datetime import datetime
from fastapi import HTTPException
from models.results import ExperimentResultsSummary, VariantResult
from data.database import Assignment, Event, Experiment
import logging

logger = logging.getLogger(__name__)

def calculate_summary(
    db: Session, 
    experiment_id: int, 
    event_type: str, 
    start_datetime: datetime | None
) -> ExperimentResultsSummary:
    """
    Calculates experiment performance summary with the required time-filter logic.
    """
    
    # 1. Check if experiment exists
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found.")

    # Convert start_date string to datetime object if provided
    # start_datetime = None
    # if start_date:
    #     try:
    #         # Assuming ISO format (e.g., YYYY-MM-DDTHH:MM:SS)
    #         start_datetime = datetime.fromisoformat(start_date)
    #     except ValueError:
    #         raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")

    # 2. Build the Core Query for Conversions
    
    # We join Assignments (A) and Events (E) to ensure we link the conversion back to the variant.
    conversion_query = db.query(
        Assignment.variant_name,
        func.count(Event.id).label('conversion_count')
    ).join(
        Event, Assignment.user_id == Event.user_id
    ).filter(
        Assignment.experiment_id == experiment_id,
        Event.type == event_type,
        # CRUCIAL REQUIREMENT: Only count events that happened AFTER assignment
        Event.timestamp > Assignment.assigned_at
    )
    
    # Apply optional date filtering
    if start_datetime:
        logger.debug("calculate summary from start_datetime %s", start_datetime)
        conversion_query = conversion_query.filter(Event.timestamp >= start_datetime)
    
    conversion_results = conversion_query.group_by(Assignment.variant_name).all()
    
    print(f"conversion_results: {conversion_results}")
    # 3. Get Total Assignments (Denominator)
    # We must count all assignments, regardless of conversion, to get the total traffic.
    assignment_counts = db.query(
        Assignment.variant_name,
        func.count(Assignment.id).label('total_assignments')
    ).filter(
        Assignment.experiment_id == experiment_id
    ).group_by(Assignment.variant_name).all()

    # 4. Aggregate Results
    results_map: dict[str, VariantResult] = {}
    
    # Initialize all variants (even those with zero conversions)
    for name, total_count in assignment_counts:
        results_map[name] = VariantResult(
            total_assignments=total_count,
            conversion_count=0,
            conversion_rate=0.0
        )
        
    # Populate conversion counts and calculate rates
    for variant_name, count in conversion_results:
        total = results_map[variant_name].total_assignments
        rate = (count / total) * 100 if total > 0 else 0.0
        
        results_map[variant_name].conversion_count = count
        results_map[variant_name].conversion_rate = round(rate, 2)
        
    
    return ExperimentResultsSummary(
        experiment_id=experiment_id,
        experiment_name=experiment.name,
        report_generated_at=datetime.utcnow(),
        variant_data=results_map
    )
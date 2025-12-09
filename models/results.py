from pydantic import BaseModel
from datetime import datetime

class VariantResult(BaseModel):
    """Detailed statistics for a single variant."""
    total_assignments: int
    conversion_count: int
    conversion_rate: float # Calculated as (conversion_count / total_assignments) * 100
    
class ExperimentResultsSummary(BaseModel):
    """Schema returned by GET /experiments/{id}/results."""
    experiment_id: int
    experiment_name: str
    report_generated_at: datetime
    # Key is variant name (e.g., 'red_button')
    variant_data: dict[str, VariantResult]
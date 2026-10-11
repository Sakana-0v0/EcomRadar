from pydantic import BaseModel


class ReportResponse(BaseModel):
    report: str
    quality_score: int
    retry_count: int
    is_degraded: bool

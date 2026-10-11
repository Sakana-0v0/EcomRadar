from pydantic import BaseModel
from typing import List


class ReportRequest(BaseModel):
    urls: List[str]

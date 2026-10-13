from pydantic import BaseModel, field_validator
from typing import Optional

class ReportRequest(BaseModel):
    urls: list[str]
    topic: Optional[str] = None  # 搜索关键词
    max_sources: Optional[int] = 10
    
    @field_validator("urls")
    def validate_urls(cls, v):
        if not v:
            raise ValueError("urls cannot be empty")
        if len(v) > 20:
            raise ValueError("最多支持20个URL")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"无效URL: {url}")
        return v
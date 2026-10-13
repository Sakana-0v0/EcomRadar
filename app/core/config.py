from pydantic_settings import BaseSettings
from pydantic import field_validator
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    llm_api_key: str = ""
    llm_model_name: str = "MiniMax-M3"
    llm_base_url: str = "https://api.minimax.cn/v1"

    embed_model_name: str = "qwen3.7-text-embedding"
    embed_api_key: str = ""
    embed_base_url: str = "https://ws-fdik2f21nxb2i3yf.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_vector_size: int = 1024
    qdrant_kb_collection: str = "knowledge_base"
    qdrant_cache_collection: str = "task_cache"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    max_urls_per_request: int = 10
    request_timeout: int = 30

    scraper_rate_limit: float = 1.0
    scraper_retry_times: int = 3
    scraper_retry_backoff: float = 2.0
    scraper_max_concurrency: int = 5
    scraper_request_timeout: float = 5.0
    jina_reader_url: str = "https://r.jina.ai"
    robots_respect: bool = True
    robots_cache_ttl: float = 60.0

    @field_validator("llm_api_key")
    def validate_api_key(cls, v):
        if not v:
            raise ValueError("LLM_API_KEY is required")
        return v

    @field_validator("qdrant_port")
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("QDRANT_PORT must be 1-65535")
        return v

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
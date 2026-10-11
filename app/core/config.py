from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    llm_model_name: str = "MiniMax-M3"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimax.cn/v1"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "reports"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
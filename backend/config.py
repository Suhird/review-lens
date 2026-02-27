import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    database_url: str = "postgresql+asyncpg://reviewlens:reviewlens@localhost:5432/reviewlens"
    redis_url: str = "redis://localhost:6379"
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ReviewLens/1.0"
    youtube_api_key: str = ""
    google_search_api_key: str = ""
    google_search_cx: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()

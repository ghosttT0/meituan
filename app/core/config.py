import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "instruction-following-evaluator"
    database_path: str = Field(default_factory=lambda: os.getenv("DATABASE_PATH", "instruction_following.db"))
    judge_runs: int = Field(default_factory=lambda: int(os.getenv("JUDGE_RUNS", "2")))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://hotaruapi.com/v1"))
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

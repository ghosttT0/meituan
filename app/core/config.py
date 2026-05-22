from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "instruction-following-evaluator"
    database_path: str = "instruction_following.db"
    judge_runs: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()

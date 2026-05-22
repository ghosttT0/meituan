import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 确保从项目根目录加载 .env 文件
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Settings(BaseModel):
    app_name: str = "instruction-following-evaluator"
    database_path: str = Field(default_factory=lambda: os.getenv("DATABASE_PATH", "instruction_following.db"))
    judge_runs: int = Field(default_factory=lambda: int(os.getenv("JUDGE_RUNS", "2")))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"))
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "deepseek-chat"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

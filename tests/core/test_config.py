from app.core.config import Settings


def test_settings_read_openai_values_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://hotaruapi.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("DATABASE_PATH", "demo.db")
    monkeypatch.setenv("JUDGE_RUNS", "3")

    settings = Settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_base_url == "https://hotaruapi.com/v1"
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.database_path == "demo.db"
    assert settings.judge_runs == 3

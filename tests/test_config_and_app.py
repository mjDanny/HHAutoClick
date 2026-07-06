from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.core.config import (
    MissingConfigError,
    Settings,
    load_local_profile,
    load_profile,
    load_searches,
)
from app.main import create_app
from app.storage.db import SessionLocal
from app.storage.models import Vacancy


def test_settings_defaults_are_review_first() -> None:
    settings = Settings()

    assert settings.auto_apply_enabled is False
    assert settings.dry_run is True
    assert settings.llm_provider == "ollama"
    assert settings.use_oauth is False
    assert settings.use_browser_profile is True
    assert settings.browser_headless is False
    assert settings.browser_channel == "chromium"
    assert settings.browser_debug_pause is False
    assert str(settings.browser_profile_dir) == ".local/browser-profile"


def test_settings_empty_optional_env_values_become_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "")
    monkeypatch.setenv("HH_ACCESS_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "")

    settings = Settings()

    assert settings.telegram_admin_chat_id is None
    assert settings.hh_access_token is None
    assert settings.telegram_bot_token is None
    assert settings.openai_compatible_api_key is None


def test_settings_reject_empty_hh_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HH_USER_AGENT", "")

    with pytest.raises(ValueError, match="HH_USER_AGENT must not be empty"):
        Settings()


def test_yaml_configs_load() -> None:
    profile = load_profile(Path("configs/profile.example.yaml"))
    searches = load_searches(Path("configs/searches.example.yaml"))

    assert profile.candidate.position == "Python Backend / AI Backend Developer"
    assert profile.candidate.confirmed_skills
    assert searches.searches


def test_missing_local_profile_explains_copy_examples(tmp_path) -> None:
    settings = Settings(profile_config_path=tmp_path / "profile.yaml")

    with pytest.raises(MissingConfigError) as exc:
        load_local_profile(settings)

    assert "configs/profile.example.yaml" in str(exc.value)


def test_fastapi_app_smoke() -> None:
    app = create_app(Settings())

    assert app.title == "Personal HH Job Autopilot"


def test_create_app_uses_custom_database_url(tmp_path) -> None:
    database_path = tmp_path / "custom.db"
    settings = Settings(database_url=f"sqlite:///{database_path}")

    create_app(settings)

    assert database_path.exists()
    session = SessionLocal()
    try:
        assert session.bind is not None
        assert inspect(session.bind).has_table(Vacancy.__tablename__)
    finally:
        session.close()

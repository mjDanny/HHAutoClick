from pathlib import Path

from app.core.config import Settings, load_profile, load_searches
from app.main import create_app


def test_settings_defaults_are_review_first() -> None:
    settings = Settings()

    assert settings.auto_apply_enabled is False
    assert settings.dry_run is True
    assert settings.llm_provider == "ollama"
    assert settings.use_oauth is False
    assert settings.use_browser_profile is True
    assert settings.browser_headless is False
    assert settings.browser_channel == "chromium"
    assert str(settings.browser_profile_dir) == ".local/browser-profile"


def test_yaml_configs_load() -> None:
    profile = load_profile(Path("configs/profile.example.yaml"))
    searches = load_searches(Path("configs/searches.example.yaml"))

    assert profile.candidate.position == "Python Backend / AI Backend Developer"
    assert profile.candidate.confirmed_skills
    assert searches.searches


def test_fastapi_app_smoke() -> None:
    app = create_app(Settings())

    assert app.title == "Personal HH Job Autopilot"

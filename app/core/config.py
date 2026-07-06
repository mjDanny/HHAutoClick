from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["ollama", "openai_compatible"]
BrowserChannel = Literal["chromium", "chrome"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/app.db"
    profile_config_path: Path = Path("configs/profile.yaml")
    searches_config_path: Path = Path("configs/searches.yaml")

    hh_base_url: str = "https://api.hh.ru"
    hh_base_web_url: str = "https://hh.ru"
    hh_user_agent: str = "personal-hh-job-autopilot/0.1"
    hh_access_token: str | None = None
    hh_resume_id: str | None = None
    hh_login_check_url: str = "https://hh.ru/applicant/resumes"

    llm_provider: LLMProviderName = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_compatible_base_url: str = "https://api.example.com/v1"
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None

    telegram_bot_token: str | None = None
    telegram_admin_chat_id: int | None = None

    auto_apply_enabled: bool = False
    dry_run: bool = True
    min_score_for_review: int = 55
    min_score_for_auto_apply: int = 88
    max_applications_per_day: int = 5
    application_cooldown_seconds: int = 900

    browser_profile_dir: Path = Path(".local/browser-profile")
    browser_headless: bool = False
    browser_channel: BrowserChannel = "chromium"
    browser_debug_pause: bool = False
    use_oauth: bool = False
    use_browser_profile: bool = True

    @field_validator(
        "hh_access_token",
        "hh_resume_id",
        "openai_compatible_api_key",
        "openai_compatible_model",
        "telegram_bot_token",
        "telegram_admin_chat_id",
        mode="before",
    )
    @classmethod
    def empty_optional_env_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("hh_user_agent")
    @classmethod
    def hh_user_agent_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("HH_USER_AGENT must not be empty")
        return value

    @field_validator("min_score_for_review", "min_score_for_auto_apply")
    @classmethod
    def score_must_be_percent(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("score thresholds must be between 0 and 100")
        return value

    @field_validator("max_applications_per_day", "application_cooldown_seconds")
    @classmethod
    def limits_must_be_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("limits must be non-negative")
        return value


class CandidateContacts(BaseModel):
    telegram: str | None = None
    email: str | None = None


class CandidatePreferences(BaseModel):
    target_titles: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    remote_is_positive: bool = True


class CandidateProfile(BaseModel):
    position: str
    contacts: CandidateContacts = Field(default_factory=CandidateContacts)
    confirmed_skills: list[str] = Field(default_factory=list)
    growth_skills: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)


class ProfileConfig(BaseModel):
    candidate: CandidateProfile


class SearchConfig(BaseModel):
    name: str
    text: str
    area: str | None = None
    schedule: str | None = None
    per_page: int = 50


class BlacklistConfig(BaseModel):
    title_terms: list[str] = Field(default_factory=list)
    company_terms: list[str] = Field(default_factory=list)


class SearchesConfig(BaseModel):
    searches: list[SearchConfig] = Field(default_factory=list)
    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    limits: dict[str, int] = Field(default_factory=dict)


class MissingConfigError(FileNotFoundError):
    def __init__(self, path: Path, example_path: Path) -> None:
        super().__init__(
            f"Config file {path} does not exist. Copy {example_path} to {path} "
            "and adjust it for your local setup."
        )
        self.path = path
        self.example_path = example_path


def _ensure_config_exists(path: Path, example_path: Path) -> None:
    if not path.exists():
        raise MissingConfigError(path, example_path)


def load_profile(path: Path) -> ProfileConfig:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    return ProfileConfig.model_validate(payload)


def load_searches(path: Path) -> SearchesConfig:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    return SearchesConfig.model_validate(payload)


def load_local_profile(settings: Settings) -> ProfileConfig:
    _ensure_config_exists(settings.profile_config_path, Path("configs/profile.example.yaml"))
    return load_profile(settings.profile_config_path)


def load_local_searches(settings: Settings) -> SearchesConfig:
    _ensure_config_exists(settings.searches_config_path, Path("configs/searches.example.yaml"))
    return load_searches(settings.searches_config_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from collections.abc import Generator
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.base import FakeLLMProvider
from app.api.deps import get_db_session
from app.browser.hh_browser_client import BrowserLoginCheckResult, BrowserPageCheckResult
from app.core.config import Settings
from app.hh.normalizer import normalize_vacancy
from app.main import create_app
from app.storage.db import Base
from app.storage.repositories import EventLogRepository, VacancyRepository


class FakeBrowserManager:
    def __init__(self) -> None:
        self.closed = False

    async def open_persistent_context(self) -> object:
        return object()

    async def close(self) -> None:
        self.closed = True


class FakeBrowserClient:
    def __init__(
        self,
        *,
        login_result: BrowserLoginCheckResult | None = None,
        page_result: BrowserPageCheckResult | None = None,
    ) -> None:
        self.login_result = login_result or BrowserLoginCheckResult(
            "logged_in",
            "https://hh.ru/applicant/resumes",
            "Browser profile is logged in",
        )
        self.page_result = page_result or BrowserPageCheckResult(
            "ok",
            "https://hh.ru/vacancy/42",
            "Vacancy page opened safely",
        )

    async def check_login(self, context: object) -> BrowserLoginCheckResult:
        return self.login_result

    async def open_vacancy(self, context: object, vacancy_url: str) -> BrowserPageCheckResult:
        return self.page_result


def make_payload() -> dict[str, Any]:
    return {
        "id": "42",
        "name": "Python Backend Developer",
        "alternate_url": "https://hh.ru/vacancy/42",
        "employer": {"name": "Example"},
        "area": {"name": "Москва"},
        "description": "FastAPI PostgreSQL Docker REST API",
        "key_skills": [{"name": "Python"}, {"name": "FastAPI"}],
    }


def make_test_client(profile) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)

    session = session_factory()
    repository = VacancyRepository(session)
    vacancy = repository.add_from_normalized(normalize_vacancy(make_payload()))
    score = 75
    repository.add_score(vacancy.id, score, ["good Python match"], ["Python"], [])
    session.commit()
    session.close()

    app = create_app(Settings(profile_config_path=Path("configs/profile.example.yaml")))
    app.state.llm_provider = FakeLLMProvider(
        "Здравствуйте! Хочу откликнуться на вакансию Python Backend Developer."
    )

    def override_session() -> Generator[Session, None, None]:
        test_session = session_factory()
        try:
            yield test_session
        finally:
            test_session.close()

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def set_fake_browser(
    client: TestClient,
    *,
    login_result: BrowserLoginCheckResult | None = None,
    page_result: BrowserPageCheckResult | None = None,
) -> None:
    app = cast(FastAPI, client.app)
    app.state.browser_session_manager = FakeBrowserManager()
    app.state.hh_browser_client = FakeBrowserClient(
        login_result=login_result,
        page_result=page_result,
    )


def event_names(client: TestClient) -> list[str]:
    app = cast(FastAPI, client.app)
    override = app.dependency_overrides[get_db_session]
    session_generator = override()
    session = next(session_generator)
    try:
        return [event.event for event in EventLogRepository(session).list_events()]
    finally:
        with suppress(StopIteration):
            next(session_generator)


def event_messages(client: TestClient) -> list[str]:
    app = cast(FastAPI, client.app)
    override = app.dependency_overrides[get_db_session]
    session_generator = override()
    session = next(session_generator)
    try:
        return [event.message for event in EventLogRepository(session).list_events()]
    finally:
        with suppress(StopIteration):
            next(session_generator)


def vacancy_status(client: TestClient, vacancy_id: int = 1) -> str:
    response = client.get(f"/api/vacancies/{vacancy_id}")
    return str(response.json()["status"])


def test_api_vacancies_and_stats(profile) -> None:
    client = make_test_client(profile)

    vacancies_response = client.get("/api/vacancies?min_score=70")
    stats_response = client.get("/api/stats")

    assert vacancies_response.status_code == 200
    assert vacancies_response.json()[0]["title"] == "Python Backend Developer"
    assert vacancies_response.json()[0]["score"]["score"] == 75
    assert stats_response.status_code == 200
    assert stats_response.json()["total"] == 1


def test_api_vacancy_detail(profile) -> None:
    client = make_test_client(profile)

    response = client.get("/api/vacancies/1")

    assert response.status_code == 200
    assert response.json()["hh_id"] == "42"
    assert "raw_json" in response.json()


def test_web_pages_smoke(profile) -> None:
    client = make_test_client(profile)

    index_response = client.get("/")
    list_response = client.get("/vacancies")
    detail_response = client.get("/vacancies/1")

    assert index_response.status_code == 200
    assert "Read-only dashboard" in index_response.text
    assert list_response.status_code == 200
    assert "Python Backend Developer" in list_response.text
    assert detail_response.status_code == 200
    assert "good Python match" in detail_response.text


def test_api_skip_and_blacklist_endpoints(profile) -> None:
    client = make_test_client(profile)

    skip_response = client.post("/api/vacancies/1/skip", json={"reason": "not relevant"})
    blacklist_response = client.post(
        "/api/vacancies/1/blacklist-company",
        json={"reason": "not a target company"},
    )
    blacklist_entries = client.get("/api/blacklist")

    assert skip_response.status_code == 200
    assert skip_response.json()["status"] == "skipped"
    assert blacklist_response.status_code == 200
    assert blacklist_response.json()["status"] == "blacklisted"
    assert blacklist_entries.status_code == 200
    assert blacklist_entries.json()[0]["kind"] == "company"
    assert blacklist_entries.json()[0]["value"] == "Example"
    assert "vacancy_skipped" in event_names(client)
    assert "company_blacklisted" in event_names(client)


def test_api_generate_rewrite_and_list_cover_letters(profile) -> None:
    client = make_test_client(profile)

    generate_response = client.post("/api/vacancies/1/cover-letter/generate")
    rewrite_response = client.post(
        "/api/vacancies/1/cover-letter/rewrite",
        json={"instruction": "make it shorter"},
    )
    list_response = client.get("/api/vacancies/1/cover-letters")

    assert generate_response.status_code == 200
    assert generate_response.json()["status"] == "valid"
    assert rewrite_response.status_code == 200
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2
    assert "cover_letter_generated" in event_names(client)
    assert "cover_letter_rewritten" in event_names(client)
    assert all("Хочу откликнуться" not in message for message in event_messages(client))


def test_api_invalid_cover_letter_stores_validation_errors(profile) -> None:
    client = make_test_client(profile)
    app = cast(FastAPI, client.app)
    app.state.llm_provider = FakeLLMProvider(
        "Здравствуйте! Уверенно владею Kafka и Kubernetes."
    )

    response = client.post("/api/vacancies/1/cover-letter/generate")

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert (
        "unsupported confident claim detected for Kafka"
        in response.json()["validation"]["errors"]
    )


def test_api_cover_letter_storage_cleans_instruction_leakage(profile) -> None:
    client = make_test_client(profile)
    app = cast(FastAPI, client.app)
    app.state.llm_provider = FakeLLMProvider(
        "\n".join(
            [
                "Здравствуйте! Хочу откликнуться на вакансию Python Backend Developer.",
                "Сделайте письмо живым, деловым, ATS-friendly, не длиннее 1700 символов.",
            ]
        )
    )

    response = client.post("/api/vacancies/1/cover-letter/generate")
    draft = response.json()

    assert response.status_code == 200
    assert draft["status"] == "valid"
    assert "Сделайте письмо" not in draft["body"]
    assert "ATS-friendly" not in draft["body"]


def test_web_vacancy_detail_shows_draft_and_validation_status(profile) -> None:
    client = make_test_client(profile)

    client.post("/api/vacancies/1/cover-letter/generate")
    response = client.get("/vacancies/1")

    assert response.status_code == 200
    assert "Latest cover letter draft" in response.text
    assert "No validation errors" in response.text


def test_browser_check_login_endpoint_returns_logged_in(profile) -> None:
    client = make_test_client(profile)
    set_fake_browser(client)

    response = client.post("/api/browser/check-login")

    assert response.status_code == 200
    assert response.json()["status"] == "logged_in"
    assert "browser_login_checked" in event_names(client)


def test_browser_check_login_endpoint_returns_logged_out(profile) -> None:
    client = make_test_client(profile)
    set_fake_browser(
        client,
        login_result=BrowserLoginCheckResult(
            "logged_out",
            "https://hh.ru/account/login",
            "Login page detected",
        ),
    )

    response = client.post("/api/browser/check-login")

    assert response.status_code == 200
    assert response.json()["status"] == "logged_out"


def test_browser_open_vacancy_endpoint_uses_saved_vacancy(profile) -> None:
    client = make_test_client(profile)
    set_fake_browser(client)

    response = client.post("/api/browser/open-vacancy/1")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert vacancy_status(client) == "new"
    assert "browser_vacancy_opened" in event_names(client)


def test_browser_open_vacancy_marks_manual_review_for_captcha(profile) -> None:
    client = make_test_client(profile)
    set_fake_browser(
        client,
        page_result=BrowserPageCheckResult(
            "captcha",
            "https://hh.ru/account/captcha",
            "CAPTCHA detected",
        ),
    )

    response = client.post("/api/browser/open-vacancy/1")
    vacancy_response = client.get("/api/vacancies/1")

    assert response.status_code == 200
    assert response.json()["status"] == "captcha"
    assert vacancy_response.json()["status"] == "needs_manual_review"
    assert "browser_challenge_detected" in event_names(client)
    assert all("cookie" not in message.lower() for message in event_messages(client))

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
from app.core.config import Settings
from app.hh.normalizer import normalize_vacancy
from app.main import create_app
from app.storage.db import Base
from app.storage.repositories import EventLogRepository, VacancyRepository


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


def test_web_vacancy_detail_shows_draft_and_validation_status(profile) -> None:
    client = make_test_client(profile)

    client.post("/api/vacancies/1/cover-letter/generate")
    response = client.get("/vacancies/1")

    assert response.status_code == 200
    assert "Latest cover letter draft" in response.text
    assert "No validation errors" in response.text

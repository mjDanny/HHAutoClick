from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.hh.normalizer import normalize_vacancy
from app.main import create_app
from app.storage.db import Base
from app.storage.repositories import VacancyRepository


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

    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        test_session = session_factory()
        try:
            yield test_session
        finally:
            test_session.close()

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


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

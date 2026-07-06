from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import CandidateProfile, SearchesConfig
from app.hh.api_client import HHApiForbiddenError
from app.hh.normalizer import normalize_vacancy
from app.services.readonly_pipeline import ReadOnlyVacancyPipeline
from app.storage.db import Base
from app.storage.repositories import BlacklistRepository, VacancyRepository


class FakeHHClient:
    def __init__(self, details: dict[str, dict[str, Any]]) -> None:
        self.details = details
        self.search_calls: list[dict[str, Any]] = []
        self.detail_calls: list[str] = []

    async def search_vacancies(self, params: dict[str, Any]) -> dict[str, Any]:
        self.search_calls.append(params)
        return {"items": [{"id": vacancy_id} for vacancy_id in self.details]}

    async def get_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        self.detail_calls.append(vacancy_id)
        return self.details[vacancy_id]


class ForbiddenHHClient(FakeHHClient):
    async def search_vacancies(self, params: dict[str, Any]) -> dict[str, Any]:
        self.search_calls.append(params)
        raise HHApiForbiddenError()


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def vacancy_payload(
    vacancy_id: str,
    *,
    title: str = "Python Backend Developer",
    company: str = "Example",
    description: str = "FastAPI PostgreSQL Docker REST API удаленная работа",
) -> dict[str, Any]:
    return {
        "id": vacancy_id,
        "name": title,
        "alternate_url": f"https://hh.ru/vacancy/{vacancy_id}",
        "employer": {"name": company},
        "area": {"name": "Москва"},
        "description": description,
        "key_skills": [{"name": "Python"}, {"name": "FastAPI"}],
        "salary": {"from": 100000, "to": 150000, "currency": "RUR", "gross": False},
    }


def make_searches(*, title_blacklist: list[str] | None = None) -> SearchesConfig:
    return SearchesConfig.model_validate(
        {
            "searches": [{"name": "Python", "text": "Python FastAPI", "area": "1"}],
            "blacklist": {"title_terms": title_blacklist or [], "company_terms": []},
        }
    )


async def test_readonly_pipeline_saves_vacancy_and_score(profile: CandidateProfile) -> None:
    session = make_session()
    client = FakeHHClient({"1": vacancy_payload("1")})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(),
    )

    summary = await pipeline.run()
    vacancies = VacancyRepository(session).list_vacancies()

    assert summary.found == 1
    assert summary.new == 1
    assert summary.saved == 1
    assert summary.errors == 0
    assert client.search_calls[0]["text"] == "Python FastAPI"
    assert len(vacancies) == 1
    assert vacancies[0].score is not None
    assert vacancies[0].score.score >= 55


async def test_readonly_pipeline_reports_hh_api_forbidden(profile: CandidateProfile) -> None:
    session = make_session()
    client = ForbiddenHHClient({})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(),
    )

    summary = await pipeline.run()

    assert summary.errors == 1
    assert summary.saved == 0
    assert summary.error_messages == [
        "hh API returned 403 forbidden. Search cannot continue from this network/environment."
    ]


async def test_readonly_pipeline_detects_duplicates(profile: CandidateProfile) -> None:
    session = make_session()
    client = FakeHHClient({"1": vacancy_payload("1")})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(),
    )

    first = await pipeline.run()
    second = await pipeline.run()

    assert first.saved == 1
    assert second.duplicates == 1
    assert second.saved == 0


async def test_readonly_pipeline_skips_known_hh_id_before_detail_request(
    profile: CandidateProfile,
) -> None:
    session = make_session()
    repository = VacancyRepository(session)
    repository.add_from_normalized(normalize_vacancy(vacancy_payload("1")))
    session.commit()

    client = FakeHHClient({"1": vacancy_payload("1")})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(),
    )

    summary = await pipeline.run()

    assert summary.duplicates == 1
    assert summary.saved == 0
    assert client.detail_calls == []


async def test_readonly_pipeline_skips_blacklisted_title(profile: CandidateProfile) -> None:
    session = make_session()
    client = FakeHHClient({"1": vacancy_payload("1", title="PHP Developer")})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(title_blacklist=["PHP"]),
    )

    summary = await pipeline.run()

    assert summary.blacklisted == 1
    assert summary.saved == 0
    assert VacancyRepository(session).stats()["total"] == 0


async def test_readonly_pipeline_saves_persistent_blacklisted_company(
    profile: CandidateProfile,
) -> None:
    session = make_session()
    BlacklistRepository(session).blacklist_company("Example", "not relevant")
    session.commit()

    client = FakeHHClient({"1": vacancy_payload("1", company="Example")})
    pipeline = ReadOnlyVacancyPipeline(
        hh_client=client,
        session=session,
        profile=profile,
        searches_config=make_searches(),
    )

    summary = await pipeline.run()
    vacancies = VacancyRepository(session).list_vacancies()

    assert summary.blacklisted == 1
    assert summary.saved == 1
    assert vacancies[0].vacancy.status == "blacklisted"


def test_repository_list_vacancies_limit_offset_min_score_and_newest_first() -> None:
    session = make_session()
    repository = VacancyRepository(session)
    scores = [40, 70, 90]

    for index, score in enumerate(scores, start=1):
        vacancy = repository.add_from_normalized(
            normalize_vacancy(vacancy_payload(str(index), title=f"Python Backend {index}"))
        )
        repository.add_score(vacancy.id, score, [f"score {score}"], ["Python"], [])
    session.commit()

    newest_first = repository.list_vacancies(limit=3)
    limited = repository.list_vacancies(limit=1)
    offset = repository.list_vacancies(limit=1, offset=1)
    high_score = repository.list_vacancies(limit=10, min_score=70)

    assert [item.vacancy.hh_id for item in newest_first] == ["3", "2", "1"]
    assert [item.vacancy.hh_id for item in limited] == ["3"]
    assert [item.vacancy.hh_id for item in offset] == ["2"]
    assert [item.vacancy.hh_id for item in high_score] == ["3", "2"]

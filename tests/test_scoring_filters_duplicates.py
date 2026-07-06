from typing import Any

from app.ai.scorer import RuleBasedVacancyScorer
from app.hh.filters import BlacklistFilter, DuplicateGuard
from app.hh.models import NormalizedVacancy


def make_vacancy(**overrides: object) -> NormalizedVacancy:
    payload: dict[str, Any] = {
        "hh_id": "1",
        "title": "Python Backend Developer",
        "company": "Example",
        "description": "FastAPI PostgreSQL Docker REST API удаленная работа",
        "key_skills": ["Python", "FastAPI", "PostgreSQL"],
    }
    payload.update(overrides)
    return NormalizedVacancy.model_validate(payload)


def test_rule_based_scoring_rewards_confirmed_skills(profile) -> None:
    result = RuleBasedVacancyScorer().score(make_vacancy(), profile)

    assert result.score >= 55
    assert "Python" in result.matched_skills
    assert "FastAPI" in result.matched_skills


def test_rule_based_scoring_flags_growth_only_skill(profile) -> None:
    result = RuleBasedVacancyScorer().score(
        make_vacancy(description="Python FastAPI Kafka Kubernetes"),
        profile,
    )

    assert "requires growth-only skill: Kafka" in result.concerns
    assert "requires growth-only skill: Kubernetes" in result.concerns


def test_blacklist_filter_blocks_title_terms() -> None:
    decision = BlacklistFilter(title_terms=["QA"]).check(make_vacancy(title="Python QA Engineer"))

    assert decision.allowed is False
    assert decision.reason == "title blacklist matched: QA"


def test_duplicate_guard_detects_id_url_and_title_company() -> None:
    first = make_vacancy(hh_id="1", url="https://hh.ru/vacancy/1?from=search")
    same_id = make_vacancy(hh_id="1", url="https://hh.ru/vacancy/2")
    same_title_company = make_vacancy(hh_id="3", url="https://hh.ru/vacancy/3")
    guard = DuplicateGuard()

    assert guard.is_duplicate(first) is False
    guard.remember(first)

    assert guard.is_duplicate(same_id) is True
    assert guard.is_duplicate(same_title_company) is True

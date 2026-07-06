from app.hh.normalizer import canonicalize_url, normalize_vacancy


def test_normalize_vacancy_extracts_core_fields() -> None:
    vacancy = normalize_vacancy(
        {
            "id": "123",
            "name": "Python Backend Developer",
            "alternate_url": "https://hh.ru/vacancy/123?from=search",
            "employer": {"name": "Example"},
            "area": {"name": "Москва"},
            "description": "<p>FastAPI и PostgreSQL</p>",
            "key_skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "salary": {"from": 100000, "to": 150000, "currency": "RUR", "gross": False},
            "has_test": True,
            "response_letter_required": True,
        }
    )

    assert vacancy.hh_id == "123"
    assert vacancy.company == "Example"
    assert vacancy.url and str(vacancy.url).startswith("https://hh.ru/vacancy/123")
    assert vacancy.description == "FastAPI и PostgreSQL"
    assert vacancy.key_skills == ["Python", "FastAPI"]
    assert vacancy.has_test is True


def test_canonicalize_url_removes_query_and_fragment() -> None:
    assert canonicalize_url("https://hh.ru/vacancy/123?from=search#x") == "https://hh.ru/vacancy/123"


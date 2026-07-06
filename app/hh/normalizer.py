from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from app.hh.models import NormalizedVacancy, Salary


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self._parts.append(cleaned)

    def text(self) -> str:
        return " ".join(self._parts)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(value)
    return parser.text()


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _extract_name(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    return None


def normalize_vacancy(payload: dict) -> NormalizedVacancy:
    salary_payload = payload.get("salary") or {}
    employer = payload.get("employer") or {}
    area = payload.get("area") or {}
    key_skills = payload.get("key_skills") or []

    salary = None
    if isinstance(salary_payload, dict) and salary_payload:
        salary = Salary(
            from_amount=salary_payload.get("from"),
            to_amount=salary_payload.get("to"),
            currency=salary_payload.get("currency"),
            gross=salary_payload.get("gross"),
        )

    return NormalizedVacancy(
        hh_id=str(payload["id"]),
        title=str(payload.get("name") or ""),
        company=employer.get("name") if isinstance(employer, dict) else None,
        area=area.get("name") if isinstance(area, dict) else None,
        url=canonicalize_url(payload.get("alternate_url") or payload.get("url")),
        apply_url=canonicalize_url(
            payload.get("apply_alternate_url") or payload.get("response_url")
        ),
        salary=salary,
        experience=_extract_name(payload, "experience"),
        employment=_extract_name(payload, "employment"),
        schedule=_extract_name(payload, "schedule"),
        description=html_to_text(
            payload.get("description") or payload.get("snippet", {}).get("responsibility")
        ),
        key_skills=[
            str(item["name"]) for item in key_skills if isinstance(item, dict) and item.get("name")
        ],
        has_test=bool(payload.get("has_test")),
        response_letter_required=bool(payload.get("response_letter_required")),
        published_at=payload.get("published_at"),
        raw=payload,
    )

import re
from dataclasses import dataclass, field

from app.hh.models import NormalizedVacancy
from app.hh.normalizer import canonicalize_url


def _contains_term(text: str, term: str) -> bool:
    normalized = text.lower()
    escaped = re.escape(term.lower())
    return re.search(rf"(?<!\w){escaped}(?!\w)", normalized) is not None


@dataclass(frozen=True)
class FilterDecision:
    allowed: bool
    reason: str | None = None


@dataclass
class BlacklistFilter:
    title_terms: list[str] = field(default_factory=list)
    company_terms: list[str] = field(default_factory=list)

    def check(self, vacancy: NormalizedVacancy) -> FilterDecision:
        for term in self.title_terms:
            if _contains_term(vacancy.title, term):
                return FilterDecision(False, f"title blacklist matched: {term}")

        company = vacancy.company or ""
        for term in self.company_terms:
            if _contains_term(company, term):
                return FilterDecision(False, f"company blacklist matched: {term}")

        return FilterDecision(True)


@dataclass
class DuplicateGuard:
    seen_hh_ids: set[str] = field(default_factory=set)
    seen_urls: set[str] = field(default_factory=set)
    seen_title_company: set[tuple[str, str]] = field(default_factory=set)

    def is_duplicate(self, vacancy: NormalizedVacancy) -> bool:
        if vacancy.hh_id in self.seen_hh_ids:
            return True

        canonical_url = canonicalize_url(str(vacancy.url) if vacancy.url else None)
        if canonical_url and canonical_url in self.seen_urls:
            return True

        title_company = (vacancy.title.strip().lower(), (vacancy.company or "").strip().lower())
        return title_company in self.seen_title_company

    def remember(self, vacancy: NormalizedVacancy) -> None:
        self.seen_hh_ids.add(vacancy.hh_id)
        canonical_url = canonicalize_url(str(vacancy.url) if vacancy.url else None)
        if canonical_url:
            self.seen_urls.add(canonical_url)
        self.seen_title_company.add(
            (vacancy.title.strip().lower(), (vacancy.company or "").strip().lower())
        )


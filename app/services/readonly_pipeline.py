import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.ai.scorer import RuleBasedVacancyScorer
from app.core.config import CandidateProfile, SearchesConfig
from app.hh.api_client import HHApiForbiddenError
from app.hh.filters import BlacklistFilter
from app.hh.normalizer import normalize_vacancy
from app.storage.repositories import BlacklistRepository, EventLogRepository, VacancyRepository

logger = logging.getLogger(__name__)


class HHReadOnlyClient(Protocol):
    async def search_vacancies(self, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def get_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class ReadOnlyPipelineSummary:
    found: int = 0
    new: int = 0
    duplicates: int = 0
    blacklisted: int = 0
    saved: int = 0
    errors: int = 0
    searches: int = 0
    error_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReadOnlyVacancyPipeline:
    def __init__(
        self,
        *,
        hh_client: HHReadOnlyClient,
        session: Session,
        profile: CandidateProfile,
        searches_config: SearchesConfig,
        scorer: RuleBasedVacancyScorer | None = None,
    ) -> None:
        self.hh_client = hh_client
        self.repository = VacancyRepository(session)
        self.events = EventLogRepository(session)
        self.blacklist_repository = BlacklistRepository(session)
        self.profile = profile
        self.searches_config = searches_config
        self.scorer = scorer or RuleBasedVacancyScorer()
        self.blacklist = BlacklistFilter(
            title_terms=searches_config.blacklist.title_terms,
            company_terms=searches_config.blacklist.company_terms,
        )

    async def run(self) -> ReadOnlyPipelineSummary:
        summary = ReadOnlyPipelineSummary(searches=len(self.searches_config.searches))

        for search in self.searches_config.searches:
            params: dict[str, Any] = {
                "text": search.text,
                "per_page": search.per_page,
            }
            if search.area:
                params["area"] = search.area
            if search.schedule:
                params["schedule"] = search.schedule

            try:
                payload = await self.hh_client.search_vacancies(params)
            except HHApiForbiddenError as exc:
                self._record_error(summary, str(exc))
                self.repository.session.commit()
                continue
            except Exception as exc:  # noqa: BLE001
                self._record_error(summary, f"search {search.name!r} failed: {exc}")
                continue

            items = payload.get("items", [])
            if not isinstance(items, list):
                self._record_error(summary, f"search {search.name!r} returned invalid items")
                continue

            summary.found += len(items)
            for item in items:
                await self._process_item(item, summary)

        return summary

    async def _process_item(self, item: Any, summary: ReadOnlyPipelineSummary) -> None:
        if not isinstance(item, dict) or not item.get("id"):
            self._record_error(summary, "vacancy item has no id")
            return

        vacancy_id = str(item["id"])
        if self.repository.exists_by_hh_id(vacancy_id):
            summary.duplicates += 1
            return

        try:
            detail = await self.hh_client.get_vacancy(vacancy_id)
            vacancy = normalize_vacancy(detail)
            if self.repository.find_duplicate(vacancy):
                summary.duplicates += 1
                return

            blacklist_decision = self.blacklist.check(vacancy)
            if not blacklist_decision.allowed:
                summary.blacklisted += 1
                return

            if self.blacklist_repository.is_company_blacklisted(vacancy.company):
                self.repository.add_from_normalized(vacancy, status="blacklisted")
                self.repository.session.commit()
                summary.blacklisted += 1
                summary.saved += 1
                return

            model = self.repository.add_from_normalized(vacancy)
            score = self.scorer.score(vacancy, self.profile)
            self.repository.add_score_result(model.id, score)
            self.repository.session.commit()
            summary.new += 1
            summary.saved += 1
        except Exception as exc:  # noqa: BLE001
            self.repository.session.rollback()
            self._record_error(summary, f"vacancy {vacancy_id} failed: {exc}")

    def _record_error(self, summary: ReadOnlyPipelineSummary, message: str) -> None:
        logger.error(message)
        summary.errors += 1
        summary.error_messages.append(message)
        self.events.add_event("ERROR", "readonly_pipeline_error", message[:500])

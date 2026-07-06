from dataclasses import asdict

from sqlalchemy.orm import Session

from app.browser.hh_browser_client import (
    BrowserLoginCheckResult,
    BrowserPageCheckResult,
    HHBrowserClient,
)
from app.browser.session_manager import BrowserSessionConfig, BrowserSessionManager
from app.core.config import Settings
from app.storage.repositories import EventLogRepository, VacancyRepository

MANUAL_REVIEW_BROWSER_STATUSES = {
    "login_required",
    "captcha",
    "challenge",
    "employer_questions",
    "test_task",
    "unknown",
}


class BrowserWorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        session: Session,
        manager: BrowserSessionManager | None = None,
        client: HHBrowserClient | None = None,
    ) -> None:
        self.settings = settings
        self.session = session
        self.manager = manager or BrowserSessionManager(
            BrowserSessionConfig.from_settings(settings)
        )
        self.client = client or HHBrowserClient(
            settings.hh_login_check_url,
            settings.hh_base_web_url,
        )
        self.events = EventLogRepository(session)
        self.vacancies = VacancyRepository(session)

    async def check_login(self) -> BrowserLoginCheckResult:
        context = await self.manager.open_persistent_context()
        try:
            result = await self.client.check_login(context)
            event = (
                "browser_challenge_detected"
                if result.status in {"captcha", "challenge"}
                else "browser_login_checked"
            )
            self.events.add_event(
                "INFO",
                event,
                f"browser_status={result.status}",
            )
            return result
        finally:
            await self.manager.close()

    async def open_login_page(self) -> BrowserLoginCheckResult:
        context = await self.manager.open_persistent_context()
        try:
            return await self.client.open_login_page(context)
        finally:
            await self.manager.close()

    async def open_vacancy(self, vacancy_id: int) -> BrowserPageCheckResult | None:
        item = self.vacancies.get_with_score(vacancy_id)
        if not item or not item.vacancy.url:
            return None

        context = await self.manager.open_persistent_context()
        try:
            result = await self.client.open_vacancy(context, item.vacancy.url)
            self.events.add_event(
                "INFO",
                "browser_vacancy_opened",
                f"vacancy_id={vacancy_id} browser_status={result.status}",
            )
            if result.status in MANUAL_REVIEW_BROWSER_STATUSES:
                item.vacancy.status = "needs_manual_review"
                self.session.flush()
                event = (
                    "browser_challenge_detected"
                    if result.status in {"captcha", "challenge"}
                    else "browser_manual_review_required"
                )
                self.events.add_event(
                    "WARNING",
                    event,
                    (
                        f"vacancy_id={vacancy_id} status=needs_manual_review "
                        f"browser_status={result.status}"
                    ),
                )
            return result
        finally:
            await self.manager.close()

    @staticmethod
    def result_to_dict(result: BrowserLoginCheckResult | BrowserPageCheckResult) -> dict[str, str]:
        return asdict(result)

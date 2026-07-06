from dataclasses import dataclass
from typing import Any, Literal, Protocol

LoginStatus = Literal["logged_in", "logged_out", "captcha", "challenge", "unknown"]
PageStatus = Literal[
    "ok",
    "login_required",
    "captcha",
    "challenge",
    "employer_questions",
    "test_task",
    "unknown",
]


class PageLike(Protocol):
    url: str

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> object:
        raise NotImplementedError

    async def title(self) -> str:
        raise NotImplementedError

    async def content(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class BrowserLoginCheckResult:
    status: LoginStatus
    url: str
    message: str


@dataclass(frozen=True)
class BrowserPageCheckResult:
    status: PageStatus
    url: str
    message: str


class HHBrowserClient:
    def __init__(self, login_check_url: str, base_web_url: str) -> None:
        self.login_check_url = login_check_url
        self.base_web_url = base_web_url.rstrip("/")

    async def check_login(self, context: Any) -> BrowserLoginCheckResult:
        page = await context.new_page()
        await page.goto(self.login_check_url, wait_until="domcontentloaded")
        result = await self.inspect_login_page(page)
        return result

    async def open_login_page(self, context: Any) -> BrowserLoginCheckResult:
        page = await context.new_page()
        await page.goto(self.login_check_url, wait_until="domcontentloaded")
        return await self.inspect_login_page(page)

    async def open_vacancy(
        self,
        context: Any,
        vacancy_url: str,
    ) -> BrowserPageCheckResult:
        page = await context.new_page()
        await page.goto(vacancy_url, wait_until="domcontentloaded")
        return await self.inspect_vacancy_page(page)

    async def inspect_login_page(self, page: PageLike) -> BrowserLoginCheckResult:
        page_text = await self._page_text(page)
        page_url = page.url
        page_status = self._detect_page_status(page_url, page_text)

        if page_status == "login_required":
            return BrowserLoginCheckResult("logged_out", page_url, "Login page detected")
        if page_status == "captcha":
            return BrowserLoginCheckResult("captcha", page_url, "CAPTCHA detected")
        if page_status == "challenge":
            return BrowserLoginCheckResult("challenge", page_url, "Safety challenge detected")
        if page_status in {"employer_questions", "test_task"}:
            return BrowserLoginCheckResult("unknown", page_url, "Unexpected page state")
        if page_status == "ok":
            return BrowserLoginCheckResult("logged_in", page_url, "Browser profile is logged in")
        return BrowserLoginCheckResult("unknown", page_url, "Could not determine login status")

    async def inspect_vacancy_page(self, page: PageLike) -> BrowserPageCheckResult:
        page_text = await self._page_text(page)
        status = self._detect_page_status(page.url, page_text)
        messages = {
            "ok": "Vacancy page opened safely",
            "login_required": "Login is required",
            "captcha": "CAPTCHA detected",
            "challenge": "Safety challenge detected",
            "employer_questions": "Employer questions detected",
            "test_task": "Test task detected",
            "unknown": "Could not determine page state",
        }
        return BrowserPageCheckResult(status, page.url, messages[status])

    async def _page_text(self, page: PageLike) -> str:
        title = await page.title()
        content = await page.content()
        return f"{page.url}\n{title}\n{content}".lower()

    def _detect_page_status(self, url: str, text: str) -> PageStatus:
        lowered_url = url.lower()
        if "/account/login" in lowered_url or "/login" in lowered_url:
            return "login_required"

        if any(marker in text for marker in ["captcha", "капча"]):
            return "captcha"

        challenge_markers = ["challenge", "проверка безопасности", "подтвердите", "проверка"]
        if any(marker in text for marker in challenge_markers):
            return "challenge"

        test_markers = ["тестовое задание", "пройти тест"]
        if any(marker in text for marker in test_markers):
            return "test_task"

        question_markers = ["вопросы работодателя", "ответьте на вопросы"]
        if any(marker in text for marker in question_markers):
            return "employer_questions"

        if self.base_web_url in lowered_url or "hh.ru" in lowered_url:
            return "ok"

        return "unknown"

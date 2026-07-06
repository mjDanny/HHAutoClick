from dataclasses import dataclass
from typing import Any, Literal, Protocol

VISIBLE_TEXT_LIMIT = 20_000

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

    def locator(self, selector: str) -> Any:
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


def detect_login_state(url: str, title: str, visible_text: str) -> BrowserLoginCheckResult:
    lowered_url = url.lower()
    text = _normalize_visible_text(title, visible_text)

    if _is_login_url(lowered_url):
        return BrowserLoginCheckResult("logged_out", url, "Logged out: login URL detected")

    if _has_captcha_signal(text):
        return BrowserLoginCheckResult(
            "captcha",
            url,
            "CAPTCHA detected: visible captcha text detected",
        )

    if _has_challenge_signal(text):
        return BrowserLoginCheckResult(
            "challenge",
            url,
            "Challenge detected: visible security check text detected",
        )

    if "/applicant/resumes" in lowered_url:
        return BrowserLoginCheckResult(
            "logged_in",
            url,
            "Logged in: applicant resumes page detected",
        )

    logged_in_signals = [
        "мои резюме",
        "создать резюме",
        "обновить резюме",
        "поднять в поиске",
        "applicant/resumes",
    ]
    if any(signal in text for signal in logged_in_signals):
        return BrowserLoginCheckResult("logged_in", url, "Logged in: resume page signal detected")

    return BrowserLoginCheckResult("unknown", url, "Unknown: no strong signals detected")


def detect_page_state(url: str, title: str, visible_text: str) -> BrowserPageCheckResult:
    lowered_url = url.lower()
    text = _normalize_visible_text(title, visible_text)

    if _is_login_url(lowered_url):
        return BrowserPageCheckResult("login_required", url, "Logged out: login URL detected")

    if _has_captcha_signal(text):
        return BrowserPageCheckResult(
            "captcha",
            url,
            "CAPTCHA detected: visible captcha text detected",
        )

    if _has_challenge_signal(text):
        return BrowserPageCheckResult(
            "challenge",
            url,
            "Challenge detected: visible security check text detected",
        )

    test_markers = ["тестовое задание", "пройти тест"]
    if any(marker in text for marker in test_markers):
        return BrowserPageCheckResult("test_task", url, "Test task detected: visible text signal")

    question_markers = ["вопросы работодателя", "ответьте на вопросы"]
    if any(marker in text for marker in question_markers):
        return BrowserPageCheckResult(
            "employer_questions",
            url,
            "Employer questions detected: visible text signal",
        )

    vacancy_signals = [
        "откликнуться",
        "вакансия",
        "требуемый опыт работы",
        "полная занятость",
        "удаленная работа",
        "компания",
        "описание вакансии",
    ]
    if "/vacancy/" in lowered_url:
        return BrowserPageCheckResult("ok", url, "OK: vacancy page detected by URL")

    if any(signal in text for signal in vacancy_signals):
        return BrowserPageCheckResult("ok", url, "OK: vacancy page detected by visible text")

    return BrowserPageCheckResult("unknown", url, "Unknown: no strong signals detected")


def _normalize_visible_text(title: str, visible_text: str) -> str:
    return f"{title}\n{visible_text[:VISIBLE_TEXT_LIMIT]}".lower()


def _is_login_url(lowered_url: str) -> bool:
    return "/account/login" in lowered_url or "/login" in lowered_url


def _has_captcha_signal(text: str) -> bool:
    captcha_markers = [
        "введите символы",
        "подтвердите, что вы не робот",
        "капча",
        "captcha",
    ]
    return any(marker in text for marker in captcha_markers)


def _has_challenge_signal(text: str) -> bool:
    challenge_markers = [
        "проверка безопасности",
        "доступ ограничен",
        "security check",
        "challenge",
    ]
    return any(marker in text for marker in challenge_markers)


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
        title, visible_text = await self._page_snapshot(page)
        return detect_login_state(page.url, title, visible_text)

    async def inspect_vacancy_page(self, page: PageLike) -> BrowserPageCheckResult:
        title, visible_text = await self._page_snapshot(page)
        return detect_page_state(page.url, title, visible_text)

    async def _page_snapshot(self, page: PageLike) -> tuple[str, str]:
        title = await page.title()
        try:
            visible_text = await page.locator("body").inner_text(timeout=3_000)
        except Exception:  # noqa: BLE001
            visible_text = ""
        return title, visible_text[:VISIBLE_TEXT_LIMIT]

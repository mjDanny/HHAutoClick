from pathlib import Path

from app.browser.hh_browser_client import (
    BrowserLoginCheckResult,
    BrowserPageCheckResult,
    HHBrowserClient,
    detect_login_state,
    detect_page_state,
)
from app.browser.session_manager import BrowserSessionConfig, BrowserSessionManager


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://hh.ru/applicant/resumes",
        title: str = "Мои резюме",
        visible_text: str = "Резюме пользователя",
    ) -> None:
        self.url = url
        self._title = title
        self._visible_text = visible_text
        self.goto_calls: list[str] = []

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.goto_calls.append(url)

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> "FakePage":
        return self

    async def inner_text(self, timeout: int = 3000) -> str:
        return self._visible_text


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    async def new_page(self) -> FakePage:
        return self.page


def make_client() -> HHBrowserClient:
    return HHBrowserClient("https://hh.ru/applicant/resumes", "https://hh.ru")


async def test_ensure_profile_dir_creates_project_profile_dir(tmp_path: Path) -> None:
    manager = BrowserSessionManager(
        BrowserSessionConfig(
            profile_dir=tmp_path / "browser-profile",
            headless=False,
            channel="chromium",
            login_check_url="https://hh.ru/applicant/resumes",
        )
    )

    profile_dir = await manager.ensure_profile_dir()

    assert profile_dir.exists()
    assert profile_dir.name == "browser-profile"


async def test_check_login_detects_logged_in() -> None:
    page = FakePage(visible_text="Мои резюме\nСоздать резюме")
    result = await make_client().check_login(FakeContext(page))

    assert result == BrowserLoginCheckResult(
        status="logged_in",
        url="https://hh.ru/applicant/resumes",
        message="Logged in: applicant resumes page detected",
    )


async def test_check_login_detects_logged_out() -> None:
    page = FakePage(url="https://hh.ru/account/login", title="Войти")
    result = await make_client().check_login(FakeContext(page))

    assert result.status == "logged_out"


async def test_open_vacancy_detects_captcha() -> None:
    page = FakePage(
        url="https://hh.ru/account/captcha",
        title="Captcha",
        visible_text="Подтвердите, что вы не робот",
    )
    result = await make_client().open_vacancy(FakeContext(page), "https://hh.ru/vacancy/1")

    assert result == BrowserPageCheckResult(
        status="captcha",
        url="https://hh.ru/account/captcha",
        message="CAPTCHA detected: visible captcha text detected",
    )


async def test_open_vacancy_detects_employer_questions() -> None:
    page = FakePage(visible_text="Ответьте на вопросы работодателя")
    result = await make_client().open_vacancy(FakeContext(page), "https://hh.ru/vacancy/1")

    assert result.status == "employer_questions"


def test_detect_login_state_resumes_url_is_logged_in() -> None:
    result = detect_login_state(
        "https://hh.ru/applicant/resumes",
        "Мои резюме",
        "Создать резюме\nОбновить резюме",
    )

    assert result.status == "logged_in"


def test_detect_login_state_ignores_hidden_captcha_word() -> None:
    result = detect_login_state(
        "https://hh.ru/applicant/resumes",
        "Мои резюме",
        "Мои резюме\nСоздать резюме",
    )

    assert result.status == "logged_in"


def test_detect_login_state_login_url_is_logged_out() -> None:
    result = detect_login_state("https://hh.ru/account/login", "Войти", "")

    assert result.status == "logged_out"


def test_detect_page_state_vacancy_visible_text_is_ok() -> None:
    result = detect_page_state(
        "https://hh.ru/vacancy/123",
        "Python Backend Developer",
        "Откликнуться\nТребуемый опыт работы\nПолная занятость",
    )

    assert result.status == "ok"


def test_detect_page_state_ignores_hidden_captcha_word() -> None:
    result = detect_page_state(
        "https://hh.ru/vacancy/123",
        "Python Backend Developer",
        "Откликнуться\nТребуемый опыт работы",
    )

    assert result.status == "ok"


def test_detect_page_state_visible_captcha_is_captcha() -> None:
    result = detect_page_state(
        "https://hh.ru/account/captcha",
        "",
        "Введите символы\nПодтвердите, что вы не робот",
    )

    assert result.status == "captcha"


def test_detect_page_state_visible_security_check_is_challenge() -> None:
    result = detect_page_state("https://hh.ru/check", "", "Проверка безопасности")

    assert result.status == "challenge"


def test_detect_page_state_test_task_is_manual_review_state() -> None:
    result = detect_page_state("https://hh.ru/applicant", "", "Тестовое задание")

    assert result.status == "test_task"


def test_detect_page_state_employer_questions_is_manual_review_state() -> None:
    result = detect_page_state("https://hh.ru/applicant", "", "Вопросы работодателя")

    assert result.status == "employer_questions"


def test_detect_page_state_unknown_without_strong_signals() -> None:
    result = detect_page_state("https://example.com", "Unknown", "Plain page")

    assert result.status == "unknown"

from pathlib import Path

from app.browser.hh_browser_client import (
    BrowserLoginCheckResult,
    BrowserPageCheckResult,
    HHBrowserClient,
)
from app.browser.session_manager import BrowserSessionConfig, BrowserSessionManager


class FakePage:
    def __init__(
        self,
        *,
        url: str = "https://hh.ru/applicant/resumes",
        title: str = "Мои резюме",
        content: str = "Резюме пользователя",
    ) -> None:
        self.url = url
        self._title = title
        self._content = content
        self.goto_calls: list[str] = []

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.goto_calls.append(url)

    async def title(self) -> str:
        return self._title

    async def content(self) -> str:
        return self._content


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
    page = FakePage()
    result = await make_client().check_login(FakeContext(page))

    assert result == BrowserLoginCheckResult(
        status="logged_in",
        url="https://hh.ru/applicant/resumes",
        message="Browser profile is logged in",
    )


async def test_check_login_detects_logged_out() -> None:
    page = FakePage(url="https://hh.ru/account/login", title="Войти")
    result = await make_client().check_login(FakeContext(page))

    assert result.status == "logged_out"


async def test_open_vacancy_detects_captcha() -> None:
    page = FakePage(
        url="https://hh.ru/account/captcha",
        title="Captcha",
        content="Подтвердите, что вы не робот",
    )
    result = await make_client().open_vacancy(FakeContext(page), "https://hh.ru/vacancy/1")

    assert result == BrowserPageCheckResult(
        status="captcha",
        url="https://hh.ru/account/captcha",
        message="CAPTCHA detected",
    )


async def test_open_vacancy_detects_employer_questions() -> None:
    page = FakePage(content="Ответьте на вопросы работодателя")
    result = await make_client().open_vacancy(FakeContext(page), "https://hh.ru/vacancy/1")

    assert result.status == "employer_questions"

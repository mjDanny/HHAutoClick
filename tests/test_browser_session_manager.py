from pathlib import Path

import pytest

from app.browser.session_manager import BrowserSessionConfig, BrowserSessionManager
from app.core.exceptions import CaptchaDetected


class FakePage:
    def __init__(
        self,
        *,
        final_url: str = "https://hh.ru/applicant/resumes",
        title: str = "Мои резюме",
        content: str = "Резюме пользователя",
    ) -> None:
        self.url = final_url
        self._title = title
        self._content = content
        self.goto_calls: list[str] = []
        self.closed = False

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.goto_calls.append(url)

    async def title(self) -> str:
        return self._title

    async def content(self) -> str:
        return self._content

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    async def new_page(self) -> FakePage:
        return self.page


def make_manager() -> BrowserSessionManager:
    return BrowserSessionManager(
        BrowserSessionConfig(
            profile_dir=Path(".local/browser-profile"),
            headless=False,
            channel="chromium",
            login_check_url="https://hh.ru/applicant/resumes",
        )
    )


async def test_check_login_returns_authenticated_and_closes_page() -> None:
    page = FakePage()
    result = await make_manager().check_login(FakeContext(page))

    assert result.authenticated is True
    assert result.status == "authenticated"
    assert page.goto_calls == ["https://hh.ru/applicant/resumes"]
    assert page.closed is True


async def test_check_login_marks_login_page_as_manual_review() -> None:
    page = FakePage(final_url="https://hh.ru/account/login", title="Войти")
    result = await make_manager().check_login(FakeContext(page))

    assert result.authenticated is False
    assert result.status == "needs_manual_review"
    assert result.reason and "login page detected" in result.reason
    assert page.closed is True


async def test_open_vacancy_keeps_safe_page_open_for_user_review() -> None:
    page = FakePage(final_url="https://hh.ru/vacancy/123", title="Python Backend")
    opened = await make_manager().open_vacancy(FakeContext(page), "https://hh.ru/vacancy/123")

    assert opened is page
    assert page.goto_calls == ["https://hh.ru/vacancy/123"]
    assert page.closed is False


async def test_open_apply_url_closes_unsafe_page_and_raises() -> None:
    page = FakePage(
        final_url="https://hh.ru/account/captcha",
        title="Captcha",
        content="Подтвердите, что вы не робот",
    )

    with pytest.raises(CaptchaDetected):
        await make_manager().open_apply_url(FakeContext(page), "https://hh.ru/applicant/vacancy_response")

    assert page.closed is True

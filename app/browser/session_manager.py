from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from playwright.async_api import Playwright, async_playwright

from app.browser.hh_browser_client import HHBrowserClient
from app.core.config import BrowserChannel, Settings
from app.core.exceptions import ManualReviewRequired


class BrowserPageLike(Protocol):
    url: str

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> Any:
        raise NotImplementedError

    async def title(self) -> str:
        raise NotImplementedError

    async def content(self) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class BrowserContextLike(Protocol):
    async def new_page(self) -> BrowserPageLike:
        raise NotImplementedError


LoginCheckStatus = Literal["authenticated", "needs_manual_review"]


@dataclass(frozen=True)
class BrowserSessionConfig:
    profile_dir: Path
    headless: bool
    channel: BrowserChannel
    login_check_url: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "BrowserSessionConfig":
        return cls(
            profile_dir=settings.browser_profile_dir,
            headless=settings.browser_headless,
            channel=settings.browser_channel,
            login_check_url=settings.hh_login_check_url,
        )


@dataclass(frozen=True)
class LoginCheckResult:
    authenticated: bool
    status: LoginCheckStatus
    reason: str | None = None


class BrowserSessionManager:
    def __init__(
        self,
        config: BrowserSessionConfig,
        hh_browser_client: HHBrowserClient | None = None,
    ) -> None:
        self.config = config
        self.hh_browser_client = hh_browser_client or HHBrowserClient()

    @asynccontextmanager
    async def persistent_context(self) -> AsyncIterator[Any]:
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        playwright: Playwright = await async_playwright().start()
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.profile_dir),
            headless=self.config.headless,
            channel=self._playwright_channel(),
        )
        try:
            yield context
        finally:
            await context.close()
            await playwright.stop()

    async def check_login(self, context: BrowserContextLike) -> LoginCheckResult:
        page = await context.new_page()
        try:
            await page.goto(self.config.login_check_url, wait_until="domcontentloaded")
            await self.hh_browser_client.assert_safe_page(page)
            return LoginCheckResult(authenticated=True, status="authenticated")
        except ManualReviewRequired as exc:
            return LoginCheckResult(
                authenticated=False,
                status="needs_manual_review",
                reason=str(exc),
            )
        finally:
            await page.close()

    async def open_vacancy(self, context: BrowserContextLike, url: str) -> BrowserPageLike:
        return await self._open_checked_page(context, url)

    async def open_apply_url(self, context: BrowserContextLike, url: str) -> BrowserPageLike:
        return await self._open_checked_page(context, url)

    async def _open_checked_page(self, context: BrowserContextLike, url: str) -> BrowserPageLike:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await self.hh_browser_client.assert_safe_page(page)
            return page
        except ManualReviewRequired:
            await page.close()
            raise

    def _playwright_channel(self) -> str | None:
        if self.config.channel == "chromium":
            return None
        return self.config.channel

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from playwright.async_api import BrowserContext, Playwright, async_playwright

from app.core.config import BrowserChannel, Settings


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
    status: str
    reason: str | None = None


class BrowserSessionManager:
    def __init__(
        self,
        config: BrowserSessionConfig,
    ) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    async def ensure_profile_dir(self) -> Path:
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        return self.config.profile_dir

    async def open_persistent_context(self) -> BrowserContext:
        await self.ensure_profile_dir()
        if self._context:
            return self._context

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.profile_dir),
            headless=self.config.headless,
            channel=self._playwright_channel(),
        )
        return self._context

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _playwright_channel(self) -> str | None:
        if self.config.channel == "chromium":
            return None
        return self.config.channel

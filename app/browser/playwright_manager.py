from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from app.core.config import BrowserChannel


class PlaywrightManager:
    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    @asynccontextmanager
    async def browser(self) -> AsyncIterator[Browser]:
        playwright: Playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=self.headless)
        try:
            yield browser
        finally:
            await browser.close()
            await playwright.stop()

    @asynccontextmanager
    async def persistent_context(
        self,
        profile_dir: Path,
        channel: BrowserChannel = "chromium",
    ) -> AsyncIterator[BrowserContext]:
        profile_dir.mkdir(parents=True, exist_ok=True)
        playwright: Playwright = await async_playwright().start()
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            channel=None if channel == "chromium" else channel,
        )
        try:
            yield context
        finally:
            await context.close()
            await playwright.stop()

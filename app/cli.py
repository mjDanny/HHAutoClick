import argparse
import asyncio

from app.browser.hh_browser_client import HHBrowserClient
from app.browser.session_manager import BrowserSessionConfig, BrowserSessionManager
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.browser_workflow import BrowserWorkflowService
from app.storage.db import SessionLocal, init_db


async def browser_login() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings.database_url)
    session = SessionLocal()
    manager = BrowserSessionManager(BrowserSessionConfig.from_settings(settings))
    try:
        client = HHBrowserClient(settings.hh_login_check_url, settings.hh_base_web_url)
        print("A visible browser will open with the project browser profile.")
        print("Log in to hh.ru manually, then return here and press Enter.")
        context = await manager.open_persistent_context()
        await client.open_login_page(context)
        input("Press Enter after manual login...")
        result = await client.check_login(context)
        service = BrowserWorkflowService(settings=settings, session=session)
        service.events.add_event("INFO", "browser_login_checked", f"browser_status={result.status}")
        session.commit()
        print(f"{result.status}: {result.message} ({result.url})")
    finally:
        await manager.close()
        session.close()


async def browser_check_login(*, pause: bool = False) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings.database_url)
    session = SessionLocal()
    try:
        effective_pause = pause or settings.browser_debug_pause
        service = BrowserWorkflowService(settings=settings, session=session)
        result = await service.check_login(pause=effective_pause)
        session.commit()
        if not effective_pause:
            print(f"{result.status}: {result.message} ({result.url})")
    finally:
        session.close()


async def browser_open_vacancy(vacancy_id: int, *, pause: bool = False) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db(settings.database_url)
    session = SessionLocal()
    try:
        effective_pause = pause or settings.browser_debug_pause
        service = BrowserWorkflowService(settings=settings, session=session)
        result = await service.open_vacancy(vacancy_id, pause=effective_pause)
        if result is None:
            print(f"Vacancy {vacancy_id} was not found or has no URL.")
        else:
            session.commit()
            if not effective_pause:
                print(f"{result.status}: {result.message} ({result.url})")
    finally:
        session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("browser-login")
    check_login = subparsers.add_parser("browser-check-login")
    check_login.add_argument("--pause", action="store_true")
    open_vacancy = subparsers.add_parser("browser-open-vacancy")
    open_vacancy.add_argument("vacancy_id", type=int)
    open_vacancy.add_argument("--pause", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "browser-login":
        asyncio.run(browser_login())
    elif args.command == "browser-check-login":
        asyncio.run(browser_check_login(pause=args.pause))
    elif args.command == "browser-open-vacancy":
        asyncio.run(browser_open_vacancy(args.vacancy_id, pause=args.pause))


if __name__ == "__main__":
    main()

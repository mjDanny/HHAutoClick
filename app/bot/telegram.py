from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.core.config import Settings


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


def create_bot(settings: Settings) -> Bot | None:
    if not settings.telegram_bot_token:
        return None
    return Bot(token=settings.telegram_bot_token)


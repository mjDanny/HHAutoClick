from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_database_parent_dir(database_url: str) -> None:
    sqlite_prefix = "sqlite:///"
    if database_url.startswith(sqlite_prefix):
        database_path = database_url.removeprefix(sqlite_prefix)
        if database_path and database_path != ":memory:":
            from pathlib import Path

            Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def configure_database(database_url: str) -> Engine:
    global engine  # noqa: PLW0603

    if str(engine.url) != database_url:
        engine.dispose()
        engine = create_engine(database_url, future=True)
        SessionLocal.configure(bind=engine)
    return engine


def init_db(database_url: str | None = None) -> None:
    from app.storage import models  # noqa: F401

    target_database_url = database_url or get_settings().database_url
    ensure_database_parent_dir(target_database_url)
    configure_database(target_database_url)
    Base.metadata.create_all(bind=engine)

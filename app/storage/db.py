from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_database_parent_dir() -> None:
    database_url = get_settings().database_url
    sqlite_prefix = "sqlite:///"
    if database_url.startswith(sqlite_prefix):
        database_path = database_url.removeprefix(sqlite_prefix)
        if database_path and database_path != ":memory:":
            from pathlib import Path

            Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    from app.storage import models  # noqa: F401

    ensure_database_parent_dir()
    Base.metadata.create_all(bind=engine)

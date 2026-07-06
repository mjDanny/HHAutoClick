from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.pipeline import router as pipeline_router
from app.api.routes.vacancies import router as vacancies_router
from app.api.routes.web import router as web_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.storage.db import init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    app = FastAPI(title="Personal HH Job Autopilot", version="0.1.0")
    app.state.settings = app_settings
    init_db()
    app.include_router(health_router)
    app.include_router(pipeline_router)
    app.include_router(vacancies_router)
    app.include_router(web_router)
    return app


app = create_app()

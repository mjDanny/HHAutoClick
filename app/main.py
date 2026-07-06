from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    app = FastAPI(title="Personal HH Job Autopilot", version="0.1.0")
    app.state.settings = app_settings
    app.include_router(health_router)
    return app


app = create_app()


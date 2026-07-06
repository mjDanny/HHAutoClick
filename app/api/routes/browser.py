from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.browser import BrowserLoginCheckView, BrowserPageCheckView
from app.services.browser_workflow import BrowserWorkflowService

router = APIRouter(prefix="/api/browser", tags=["browser"])


def _service(request: Request, session: Session) -> BrowserWorkflowService:
    settings = request.app.state.settings
    manager = getattr(request.app.state, "browser_session_manager", None)
    client = getattr(request.app.state, "hh_browser_client", None)
    return BrowserWorkflowService(
        settings=settings,
        session=session,
        manager=manager,
        client=client,
    )


@router.post("/check-login", response_model=BrowserLoginCheckView)
async def check_login(
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    service = _service(request, session)
    try:
        result = await service.check_login()
        session.commit()
        return service.result_to_dict(result)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=503, detail=f"Browser login check failed: {exc}") from exc


@router.post("/open-vacancy/{vacancy_id}", response_model=BrowserPageCheckView)
async def open_vacancy(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    service = _service(request, session)
    try:
        result = await service.open_vacancy(vacancy_id)
        if not result:
            raise HTTPException(status_code=404, detail="Vacancy not found")
        session.commit()
        return service.result_to_dict(result)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=503, detail=f"Browser vacancy open failed: {exc}") from exc

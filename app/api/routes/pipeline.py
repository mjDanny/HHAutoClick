from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.pipeline import ReadOnlyPipelineSummaryView
from app.core.config import MissingConfigError, load_local_profile, load_local_searches
from app.hh.api_client import HHApiClient
from app.services.readonly_pipeline import ReadOnlyVacancyPipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run-readonly", response_model=ReadOnlyPipelineSummaryView)
async def run_readonly_pipeline(
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    settings = request.app.state.settings
    try:
        profile = load_local_profile(settings).candidate
        searches = load_local_searches(settings)
    except MissingConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pipeline = ReadOnlyVacancyPipeline(
        hh_client=HHApiClient(settings),
        session=session,
        profile=profile,
        searches_config=searches,
    )
    summary = await pipeline.run()
    return summary.to_dict()

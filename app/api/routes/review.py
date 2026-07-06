import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.providers.factory import build_llm_provider
from app.api.deps import get_db_session
from app.api.schemas.review import (
    BlacklistEntryView,
    CoverLetterDraftView,
    CoverLetterValidationView,
    ReviewActionRequest,
    ReviewActionResponse,
    RewriteCoverLetterRequest,
)
from app.core.config import MissingConfigError, load_local_profile
from app.services.review_workflow import ReviewWorkflowService
from app.storage.models import CoverLetter
from app.storage.repositories import BlacklistRepository, CoverLetterRepository, VacancyRepository

router = APIRouter(prefix="/api", tags=["review"])


def _draft_view(draft: CoverLetter) -> CoverLetterDraftView:
    errors = json.loads(draft.validation_errors_json)
    return CoverLetterDraftView(
        id=draft.id,
        vacancy_id=draft.vacancy_id,
        body=draft.body,
        provider=draft.provider,
        model=draft.model,
        status=draft.status,
        validation=CoverLetterValidationView(valid=draft.is_valid, errors=errors),
        created_at=draft.created_at.isoformat(),
    )


def _service(request: Request, session: Session) -> ReviewWorkflowService:
    settings = request.app.state.settings
    try:
        profile = load_local_profile(settings).candidate
    except MissingConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        try:
            provider = build_llm_provider(settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewWorkflowService(session=session, profile=profile, llm_provider=provider)


@router.post("/vacancies/{vacancy_id}/skip", response_model=ReviewActionResponse)
def skip_vacancy(
    vacancy_id: int,
    payload: ReviewActionRequest | None = None,
    session: Session = Depends(get_db_session),
) -> ReviewActionResponse:
    vacancy = VacancyRepository(session).skip_vacancy(
        vacancy_id,
        payload.reason if payload else None,
    )
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    session.commit()
    return ReviewActionResponse(vacancy_id=vacancy.id, status=vacancy.status)


@router.post("/vacancies/{vacancy_id}/blacklist-company", response_model=ReviewActionResponse)
def blacklist_company(
    vacancy_id: int,
    payload: ReviewActionRequest | None = None,
    session: Session = Depends(get_db_session),
) -> ReviewActionResponse:
    vacancy_repository = VacancyRepository(session)
    item = vacancy_repository.get_with_score(vacancy_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    vacancy = item.vacancy
    if vacancy.company:
        BlacklistRepository(session).blacklist_company(
            vacancy.company,
            payload.reason if payload else None,
        )
    vacancy.status = "blacklisted"
    session.flush()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    session.commit()
    return ReviewActionResponse(vacancy_id=vacancy.id, status=vacancy.status)


@router.post("/vacancies/{vacancy_id}/cover-letter/generate", response_model=CoverLetterDraftView)
async def generate_cover_letter(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> CoverLetterDraftView:
    service = _service(request, session)
    try:
        result = await service.generate_cover_letter(vacancy_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"Cover letter generation failed: {exc}",
        ) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    session.commit()
    return _draft_view(result.draft)


@router.post("/vacancies/{vacancy_id}/cover-letter/rewrite", response_model=CoverLetterDraftView)
async def rewrite_cover_letter(
    vacancy_id: int,
    request: Request,
    payload: RewriteCoverLetterRequest | None = None,
    session: Session = Depends(get_db_session),
) -> CoverLetterDraftView:
    service = _service(request, session)
    try:
        result = await service.generate_cover_letter(
            vacancy_id,
            payload.instruction if payload else None,
        )
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=502, detail=f"Cover letter rewrite failed: {exc}") from exc
    if not result:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    session.commit()
    return _draft_view(result.draft)


@router.get("/vacancies/{vacancy_id}/cover-letters", response_model=list[CoverLetterDraftView])
def list_cover_letters(
    vacancy_id: int,
    session: Session = Depends(get_db_session),
) -> list[CoverLetterDraftView]:
    drafts = CoverLetterRepository(session).list_cover_letter_drafts(vacancy_id)
    return [_draft_view(draft) for draft in drafts]


@router.get("/blacklist", response_model=list[BlacklistEntryView])
def list_blacklist(session: Session = Depends(get_db_session)) -> list[BlacklistEntryView]:
    return [
        BlacklistEntryView(
            id=entry.id,
            kind=entry.kind,
            value=entry.value,
            reason=entry.reason,
            created_at=entry.created_at.isoformat(),
        )
        for entry in BlacklistRepository(session).list_entries()
    ]

import json
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.ai.providers.factory import build_llm_provider
from app.api.deps import get_db_session
from app.core.config import load_local_profile
from app.services.browser_workflow import BrowserWorkflowService
from app.services.review_workflow import ReviewWorkflowService
from app.storage.models import Vacancy, VacancyScore
from app.storage.repositories import (
    BlacklistRepository,
    CoverLetterRepository,
    VacancyRepository,
    VacancyWithScore,
)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/web/templates")


def _score_context(score: VacancyScore | None) -> dict | None:
    if not score:
        return None
    return {
        "score": score.score,
        "reasons": json.loads(score.reasons_json),
        "matched_skills": json.loads(score.matched_skills_json),
        "concerns": json.loads(score.concerns_json),
    }


def _vacancy_context(item: VacancyWithScore) -> dict:
    vacancy = item.vacancy
    return {
        "id": vacancy.id,
        "hh_id": vacancy.hh_id,
        "title": vacancy.title,
        "company": vacancy.company,
        "url": vacancy.url,
        "area": vacancy.area,
        "salary_text": vacancy.salary_text,
        "status": vacancy.status,
        "created_at": vacancy.created_at,
        "score": _score_context(item.score),
        "has_test": vacancy.has_test,
        "response_letter_required": vacancy.response_letter_required,
        "raw_json": vacancy.raw_json,
    }


def _draft_context(draft) -> dict:
    return {
        "id": draft.id,
        "body": draft.body,
        "status": draft.status,
        "provider": draft.provider,
        "model": draft.model,
        "validation_errors": json.loads(draft.validation_errors_json),
        "created_at": draft.created_at,
    }


async def _form_value(request: Request, key: str) -> str | None:
    body = (await request.body()).decode("utf-8")
    values = parse_qs(body).get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    browser_status: str | None = None,
    browser_message: str | None = None,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    stats = VacancyRepository(session).stats()
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stats": stats,
            "settings": settings,
            "browser_status": browser_status,
            "browser_message": browser_message,
        },
    )


@router.get("/vacancies", response_class=HTMLResponse)
def vacancies_page(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    min_score: int | None = None,
    status: str | None = None,
    company: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    repository = VacancyRepository(session)
    vacancies = [
        _vacancy_context(item)
        for item in repository.list_vacancies(
            limit=limit,
            offset=offset,
            min_score=min_score,
            status=status,
            company=company,
            q=q,
        )
    ]
    return templates.TemplateResponse(
        request,
        "vacancies.html",
        {"vacancies": vacancies, "filters": {"q": q or "", "min_score": min_score or ""}},
    )


@router.get("/vacancies/{vacancy_id}", response_class=HTMLResponse)
def vacancy_page(
    vacancy_id: int,
    request: Request,
    browser_status: str | None = None,
    browser_message: str | None = None,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    item = VacancyRepository(session).get_with_score(vacancy_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    cover_letters = CoverLetterRepository(session)
    drafts = [_draft_context(draft) for draft in cover_letters.list_cover_letter_drafts(vacancy_id)]
    return templates.TemplateResponse(
        request,
        "vacancy_detail.html",
        {
            "vacancy": _vacancy_context(item),
            "drafts": drafts,
            "latest_draft": drafts[0] if drafts else None,
            "browser_status": browser_status,
            "browser_message": browser_message,
        },
    )


@router.post("/browser/check-login")
async def check_browser_login_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    settings = request.app.state.settings
    service = BrowserWorkflowService(settings=settings, session=session)
    result = await service.check_login()
    session.commit()
    query = urlencode({"browser_status": result.status, "browser_message": result.message})
    return RedirectResponse(
        f"/?{query}",
        status_code=303,
    )


@router.post("/vacancies/{vacancy_id}/open-browser-profile")
async def open_vacancy_browser_page(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    settings = request.app.state.settings
    service = BrowserWorkflowService(settings=settings, session=session)
    result = await service.open_vacancy(vacancy_id)
    session.commit()
    if result is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    query = urlencode({"browser_status": result.status, "browser_message": result.message})
    return RedirectResponse(
        f"/vacancies/{vacancy_id}?{query}",
        status_code=303,
    )


@router.post("/vacancies/{vacancy_id}/skip")
async def skip_vacancy_page(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    reason = await _form_value(request, "reason")
    VacancyRepository(session).skip_vacancy(vacancy_id, reason)
    session.commit()
    return RedirectResponse(f"/vacancies/{vacancy_id}", status_code=303)


@router.post("/vacancies/{vacancy_id}/blacklist-company")
async def blacklist_company_page(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    reason = await _form_value(request, "reason")
    vacancy = session.get(Vacancy, vacancy_id)
    if vacancy and vacancy.company:
        BlacklistRepository(session).blacklist_company(vacancy.company, reason)
        vacancy.status = "blacklisted"
        session.commit()
    return RedirectResponse(f"/vacancies/{vacancy_id}", status_code=303)


@router.post("/vacancies/{vacancy_id}/cover-letter/generate")
async def generate_cover_letter_page(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    settings = request.app.state.settings
    provider = getattr(request.app.state, "llm_provider", None) or build_llm_provider(settings)
    profile = load_local_profile(settings).candidate
    service = ReviewWorkflowService(session=session, profile=profile, llm_provider=provider)
    await service.generate_cover_letter(vacancy_id)
    session.commit()
    return RedirectResponse(f"/vacancies/{vacancy_id}", status_code=303)


@router.post("/vacancies/{vacancy_id}/cover-letter/rewrite")
async def rewrite_cover_letter_page(
    vacancy_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
) -> RedirectResponse:
    instruction = await _form_value(request, "instruction")
    settings = request.app.state.settings
    provider = getattr(request.app.state, "llm_provider", None) or build_llm_provider(settings)
    profile = load_local_profile(settings).candidate
    service = ReviewWorkflowService(session=session, profile=profile, llm_provider=provider)
    await service.generate_cover_letter(vacancy_id, instruction)
    session.commit()
    return RedirectResponse(f"/vacancies/{vacancy_id}", status_code=303)

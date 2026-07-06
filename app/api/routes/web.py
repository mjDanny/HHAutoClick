import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.storage.models import VacancyScore
from app.storage.repositories import VacancyRepository, VacancyWithScore

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


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_db_session)) -> HTMLResponse:
    stats = VacancyRepository(session).stats()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"stats": stats},
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
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    item = VacancyRepository(session).get_with_score(vacancy_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return templates.TemplateResponse(
        request,
        "vacancy_detail.html",
        {"vacancy": _vacancy_context(item)},
    )

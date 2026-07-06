import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.pipeline import StatsView
from app.api.schemas.vacancy import VacancyDetailView, VacancyScoreView, VacancyView
from app.storage.models import VacancyScore
from app.storage.repositories import VacancyRepository, VacancyWithScore

router = APIRouter(prefix="/api", tags=["vacancies"])


def _score_view(score: VacancyScore | None) -> VacancyScoreView | None:
    if not score:
        return None
    return VacancyScoreView(
        score=score.score,
        reasons=json.loads(score.reasons_json),
        matched_skills=json.loads(score.matched_skills_json),
        concerns=json.loads(score.concerns_json),
    )


def _vacancy_view(item: VacancyWithScore) -> VacancyView:
    vacancy = item.vacancy
    return VacancyView(
        id=vacancy.id,
        hh_id=vacancy.hh_id,
        title=vacancy.title,
        company=vacancy.company,
        url=vacancy.url,
        area=vacancy.area,
        salary_text=vacancy.salary_text,
        status=vacancy.status,
        created_at=vacancy.created_at.isoformat(),
        score=_score_view(item.score),
    )


@router.get("/vacancies", response_model=list[VacancyView])
def list_vacancies(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: int | None = Query(default=None, ge=0, le=100),
    status: str | None = None,
    company: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[VacancyView]:
    repository = VacancyRepository(session)
    vacancies = repository.list_vacancies(
        limit=limit,
        offset=offset,
        min_score=min_score,
        status=status,
        company=company,
        q=q,
    )
    return [_vacancy_view(item) for item in vacancies]


@router.get("/vacancies/{vacancy_id}", response_model=VacancyDetailView)
def get_vacancy(
    vacancy_id: int,
    session: Session = Depends(get_db_session),
) -> VacancyDetailView:
    repository = VacancyRepository(session)
    item = repository.get_with_score(vacancy_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    view = _vacancy_view(item)
    return VacancyDetailView(
        **view.model_dump(),
        raw_json=item.vacancy.raw_json,
        has_test=item.vacancy.has_test,
        response_letter_required=item.vacancy.response_letter_required,
    )


@router.get("/stats", response_model=StatsView)
def get_stats(session: Session = Depends(get_db_session)) -> dict[str, int]:
    return VacancyRepository(session).stats()

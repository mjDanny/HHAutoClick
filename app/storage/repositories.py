import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.hh.models import NormalizedVacancy
from app.storage.models import Application, Vacancy, VacancyScore


class VacancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists_by_hh_id(self, hh_id: str) -> bool:
        statement = select(Vacancy.id).where(Vacancy.hh_id == hh_id)
        return self.session.execute(statement).first() is not None

    def add_from_normalized(self, vacancy: NormalizedVacancy) -> Vacancy:
        existing = self.session.scalar(select(Vacancy).where(Vacancy.hh_id == vacancy.hh_id))
        if existing:
            return existing

        model = Vacancy(
            hh_id=vacancy.hh_id,
            title=vacancy.title,
            company=vacancy.company,
            url=str(vacancy.url) if vacancy.url else None,
            has_test=vacancy.has_test,
            response_letter_required=vacancy.response_letter_required,
            raw_json=vacancy.model_dump_json(),
        )
        self.session.add(model)
        self.session.flush()
        return model

    def add_score(
        self,
        vacancy_id: int,
        score: int,
        reasons: list[str],
        matched_skills: list[str],
        concerns: list[str],
    ) -> VacancyScore:
        model = VacancyScore(
            vacancy_id=vacancy_id,
            score=score,
            reasons_json=json.dumps(reasons, ensure_ascii=False),
            matched_skills_json=json.dumps(matched_skills, ensure_ascii=False),
            concerns_json=json.dumps(concerns, ensure_ascii=False),
        )
        self.session.add(model)
        self.session.flush()
        return model


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_application_for_vacancy(self, vacancy_id: int) -> bool:
        statement = select(Application.id).where(Application.vacancy_id == vacancy_id)
        return self.session.execute(statement).first() is not None

    def create_draft(self, vacancy_id: int, dry_run: bool = True) -> Application:
        model = Application(vacancy_id=vacancy_id, status="draft", dry_run=dry_run)
        self.session.add(model)
        self.session.flush()
        return model


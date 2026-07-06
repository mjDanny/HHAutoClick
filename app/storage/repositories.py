import json
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.ai.scorer import ScoreResult
from app.hh.models import NormalizedVacancy
from app.storage.models import Application, Vacancy, VacancyScore


def _salary_text(vacancy: NormalizedVacancy) -> str | None:
    if not vacancy.salary:
        return None
    salary = vacancy.salary
    parts: list[str] = []
    if salary.from_amount:
        parts.append(f"from {salary.from_amount}")
    if salary.to_amount:
        parts.append(f"to {salary.to_amount}")
    if salary.currency:
        parts.append(salary.currency)
    if salary.gross is not None:
        parts.append("gross" if salary.gross else "net")
    return " ".join(parts) or None


def _payload_hash(vacancy: NormalizedVacancy) -> str:
    return sha256(vacancy.model_dump_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VacancyWithScore:
    vacancy: Vacancy
    score: VacancyScore | None


class VacancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists_by_hh_id(self, hh_id: str) -> bool:
        statement = select(Vacancy.id).where(Vacancy.hh_id == hh_id)
        return self.session.execute(statement).first() is not None

    def find_duplicate(self, vacancy: NormalizedVacancy) -> Vacancy | None:
        url = str(vacancy.url) if vacancy.url else None
        title = vacancy.title.strip().lower()
        company = (vacancy.company or "").strip().lower()

        conditions = [Vacancy.hh_id == vacancy.hh_id]
        if url:
            conditions.append(Vacancy.url == url)
        if title and company:
            conditions.append(
                and_(func.lower(Vacancy.title) == title, func.lower(Vacancy.company) == company)
            )

        statement = select(Vacancy).where(or_(*conditions))
        for existing in self.session.scalars(statement):
            if existing.hh_id == vacancy.hh_id:
                return existing
            if url and existing.url == url:
                return existing
            same_title = existing.title.strip().lower() == title
            same_company = (existing.company or "").strip().lower() == company
            if same_title and same_company:
                return existing
        return None

    def add_from_normalized(self, vacancy: NormalizedVacancy) -> Vacancy:
        existing = self.find_duplicate(vacancy)
        if existing:
            return existing

        model = Vacancy(
            hh_id=vacancy.hh_id,
            title=vacancy.title,
            company=vacancy.company,
            url=str(vacancy.url) if vacancy.url else None,
            area=vacancy.area,
            salary_text=_salary_text(vacancy),
            experience=vacancy.experience,
            employment=vacancy.employment,
            schedule=vacancy.schedule,
            status="new",
            raw_payload_hash=_payload_hash(vacancy),
            has_test=vacancy.has_test,
            response_letter_required=vacancy.response_letter_required,
            raw_json=vacancy.model_dump_json(),
        )
        self.session.add(model)
        self.session.flush()
        return model

    def add_score_result(self, vacancy_id: int, score: ScoreResult) -> VacancyScore:
        return self.add_score(
            vacancy_id=vacancy_id,
            score=score.score,
            reasons=score.reasons,
            matched_skills=score.matched_skills,
            concerns=score.concerns,
        )

    def latest_score(self, vacancy_id: int) -> VacancyScore | None:
        statement = (
            select(VacancyScore)
            .where(VacancyScore.vacancy_id == vacancy_id)
            .order_by(VacancyScore.created_at.desc(), VacancyScore.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def latest_scores_for_vacancies(self, vacancy_ids: list[int]) -> dict[int, VacancyScore]:
        if not vacancy_ids:
            return {}

        latest_score_ids = (
            select(func.max(VacancyScore.id).label("id"))
            .where(VacancyScore.vacancy_id.in_(vacancy_ids))
            .group_by(VacancyScore.vacancy_id)
            .subquery()
        )
        statement = select(VacancyScore).join(
            latest_score_ids,
            VacancyScore.id == latest_score_ids.c.id,
        )
        return {
            score.vacancy_id: score
            for score in self.session.scalars(statement)
        }

    def list_vacancies(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        min_score: int | None = None,
        status: str | None = None,
        company: str | None = None,
        q: str | None = None,
    ) -> list[VacancyWithScore]:
        statement = select(Vacancy).order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
        if status:
            statement = statement.where(Vacancy.status == status)
        if company:
            statement = statement.where(Vacancy.company.ilike(f"%{company}%"))
        if q:
            statement = statement.where(
                or_(
                    Vacancy.title.ilike(f"%{q}%"),
                    Vacancy.company.ilike(f"%{q}%"),
                    Vacancy.raw_json.ilike(f"%{q}%"),
                )
            )

        if min_score is not None:
            latest_score_ids = (
                select(func.max(VacancyScore.id).label("id"))
                .group_by(VacancyScore.vacancy_id)
                .subquery()
            )
            statement = (
                statement.join(VacancyScore, VacancyScore.vacancy_id == Vacancy.id)
                .join(latest_score_ids, VacancyScore.id == latest_score_ids.c.id)
                .where(VacancyScore.score >= min_score)
            )

        statement = statement.limit(limit).offset(offset)
        vacancies = list(self.session.scalars(statement).all())
        scores = self.latest_scores_for_vacancies([vacancy.id for vacancy in vacancies])
        return [
            VacancyWithScore(vacancy, scores.get(vacancy.id))
            for vacancy in vacancies
        ]

    def get_with_score(self, vacancy_id: int) -> VacancyWithScore | None:
        vacancy = self.session.get(Vacancy, vacancy_id)
        if not vacancy:
            return None
        return VacancyWithScore(vacancy=vacancy, score=self.latest_score(vacancy.id))

    def stats(self) -> dict[str, int]:
        total = self.session.scalar(select(func.count(Vacancy.id))) or 0
        new = (
            self.session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == "new"))
            or 0
        )
        skipped = (
            self.session.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == "skipped"))
            or 0
        )
        return {"total": total, "new": new, "skipped": skipped}

    def set_status(self, vacancy_id: int, status: str) -> Vacancy | None:
        vacancy = self.session.get(Vacancy, vacancy_id)
        if not vacancy:
            return None
        vacancy.status = status
        self.session.flush()
        return vacancy

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

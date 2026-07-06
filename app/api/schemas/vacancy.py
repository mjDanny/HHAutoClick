from pydantic import BaseModel


class VacancyScoreView(BaseModel):
    score: int
    reasons: list[str]
    matched_skills: list[str]
    concerns: list[str]


class VacancyView(BaseModel):
    hh_id: str
    title: str
    company: str | None
    url: str | None
    score: VacancyScoreView | None = None


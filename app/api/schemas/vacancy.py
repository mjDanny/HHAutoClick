from pydantic import BaseModel


class VacancyScoreView(BaseModel):
    score: int
    reasons: list[str]
    matched_skills: list[str]
    concerns: list[str]


class VacancyView(BaseModel):
    id: int
    hh_id: str
    title: str
    company: str | None
    url: str | None
    area: str | None = None
    salary_text: str | None = None
    status: str
    created_at: str
    score: VacancyScoreView | None = None


class VacancyDetailView(VacancyView):
    raw_json: str
    has_test: bool
    response_letter_required: bool

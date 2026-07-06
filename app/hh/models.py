from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Salary(BaseModel):
    from_amount: int | None = None
    to_amount: int | None = None
    currency: str | None = None
    gross: bool | None = None


class NormalizedVacancy(BaseModel):
    hh_id: str
    title: str
    company: str | None = None
    area: str | None = None
    url: HttpUrl | None = None
    apply_url: HttpUrl | None = None
    salary: Salary | None = None
    experience: str | None = None
    employment: str | None = None
    schedule: str | None = None
    description: str = ""
    key_skills: list[str] = Field(default_factory=list)
    has_test: bool = False
    response_letter_required: bool = False
    published_at: datetime | None = None
    raw: dict = Field(default_factory=dict)

    @property
    def search_text(self) -> str:
        parts = [
            self.title,
            self.company or "",
            self.description,
            " ".join(self.key_skills),
            self.experience or "",
            self.employment or "",
            self.schedule or "",
        ]
        return " ".join(part for part in parts if part).lower()


from pydantic import BaseModel


class ReviewActionRequest(BaseModel):
    reason: str | None = None


class RewriteCoverLetterRequest(BaseModel):
    instruction: str | None = None


class CoverLetterValidationView(BaseModel):
    valid: bool
    errors: list[str]


class CoverLetterDraftView(BaseModel):
    id: int
    vacancy_id: int
    body: str
    provider: str
    model: str
    status: str
    validation: CoverLetterValidationView
    created_at: str


class ReviewActionResponse(BaseModel):
    vacancy_id: int
    status: str


class BlacklistEntryView(BaseModel):
    id: int
    kind: str
    value: str
    reason: str | None
    created_at: str


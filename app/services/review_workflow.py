from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.prompts.cover_letter import build_cover_letter_prompt
from app.ai.providers.base import LLMMessage, LLMProvider, LLMRequest
from app.ai.validator import CoverLetterValidator
from app.core.config import CandidateProfile
from app.hh.models import NormalizedVacancy
from app.storage.models import CoverLetter, Vacancy
from app.storage.repositories import (
    BlacklistRepository,
    CoverLetterRepository,
    VacancyRepository,
)


@dataclass(frozen=True)
class ReviewDraftResult:
    vacancy: Vacancy
    draft: CoverLetter


class ReviewWorkflowService:
    def __init__(
        self,
        *,
        session: Session,
        profile: CandidateProfile,
        llm_provider: LLMProvider,
        validator: CoverLetterValidator | None = None,
    ) -> None:
        self.session = session
        self.profile = profile
        self.llm_provider = llm_provider
        self.validator = validator or CoverLetterValidator()
        self.vacancies = VacancyRepository(session)
        self.cover_letters = CoverLetterRepository(session)
        self.blacklist = BlacklistRepository(session)

    def skip_vacancy(self, vacancy_id: int, reason: str | None = None) -> Vacancy | None:
        return self.vacancies.skip_vacancy(vacancy_id, reason)

    def blacklist_company(self, vacancy_id: int, reason: str | None = None) -> Vacancy | None:
        vacancy = self.session.get(Vacancy, vacancy_id)
        if not vacancy or not vacancy.company:
            return vacancy
        self.blacklist.blacklist_company(vacancy.company, reason)
        vacancy.status = "blacklisted"
        self.session.flush()
        return vacancy

    async def generate_cover_letter(
        self,
        vacancy_id: int,
        instruction: str | None = None,
    ) -> ReviewDraftResult | None:
        vacancy = self.session.get(Vacancy, vacancy_id)
        if not vacancy:
            return None

        normalized = NormalizedVacancy.model_validate_json(vacancy.raw_json)
        prompt = build_cover_letter_prompt(normalized, self.profile)
        if instruction:
            prompt = f"{prompt}\n\nДополнительная инструкция для переписывания: {instruction}"

        response = await self.llm_provider.complete(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "Write factual Russian cover letters and do not claim "
                            "unconfirmed experience."
                        ),
                    ),
                    LLMMessage(role="user", content=prompt),
                ],
            )
        )
        validation = self.validator.validate(response.content)
        draft = self.cover_letters.create_cover_letter_draft(
            vacancy_id=vacancy.id,
            prompt=prompt,
            body=response.content,
            provider=response.provider,
            model=response.model,
            validation=validation,
        )
        vacancy.status = "draft_ready" if validation.valid else "needs_manual_review"
        self.session.flush()
        return ReviewDraftResult(vacancy=vacancy, draft=draft)

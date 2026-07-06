from dataclasses import dataclass

from app.ai.prompts.cover_letter import build_cover_letter_prompt
from app.ai.providers.base import LLMMessage, LLMProvider, LLMRequest
from app.ai.validator import CoverLetterValidator, ValidationResult
from app.core.config import CandidateProfile
from app.hh.models import NormalizedVacancy


@dataclass(frozen=True)
class CoverLetterDraft:
    text: str
    provider: str
    model: str
    validation: ValidationResult


class CoverLetterGenerator:
    def __init__(
        self,
        provider: LLMProvider,
        validator: CoverLetterValidator | None = None,
    ) -> None:
        self.provider = provider
        self.validator = validator or CoverLetterValidator()

    async def generate(
        self, vacancy: NormalizedVacancy, profile: CandidateProfile
    ) -> CoverLetterDraft:
        prompt = build_cover_letter_prompt(vacancy, profile)
        response = await self.provider.complete(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "You write factual Russian cover letters without "
                            "fabricating experience."
                        ),
                    ),
                    LLMMessage(role="user", content=prompt),
                ]
            )
        )
        validation = self.validator.validate(response.content)
        return CoverLetterDraft(
            text=response.content,
            provider=response.provider,
            model=response.model,
            validation=validation,
        )

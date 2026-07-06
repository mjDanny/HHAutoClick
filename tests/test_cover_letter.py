import pytest

from app.ai.cover_letter import CoverLetterGenerator
from app.ai.prompts.cover_letter import build_cover_letter_prompt
from app.ai.providers.base import FakeLLMProvider
from app.ai.validator import CoverLetterValidator
from app.hh.models import NormalizedVacancy


@pytest.fixture
def vacancy() -> NormalizedVacancy:
    return NormalizedVacancy(
        hh_id="10",
        title="AI Backend Developer",
        company="AI Product",
        description="Нужны Python, FastAPI, LLM, RAG, Kafka.",
        key_skills=["Python", "FastAPI", "RAG", "Kafka"],
    )


def test_cover_letter_prompt_contains_profile_and_guardrails(vacancy, profile) -> None:
    prompt = build_cover_letter_prompt(vacancy, profile)

    assert "AI Backend Developer" in prompt
    assert "FastAPI" in prompt
    assert "Kafka" in prompt
    assert "готов быстро погрузиться" in prompt
    assert "выдумывать" in prompt


def test_validator_catches_unsupported_confident_technology() -> None:
    result = CoverLetterValidator().validate(
        "Здравствуйте! Уверенно владею Kafka и Kubernetes, работал с ними в production."
    )

    assert result.valid is False
    assert "unsupported confident claim detected for Kafka" in result.errors


async def test_cover_letter_generator_uses_provider(vacancy, profile) -> None:
    provider = FakeLLMProvider("Здравствуйте! Хочу откликнуться на вакансию AI Backend Developer.")
    draft = await CoverLetterGenerator(provider).generate(vacancy, profile)

    assert draft.provider == "fake"
    assert draft.validation.valid is True
    assert provider.requests

import pytest

from app.ai.cover_letter import CoverLetterGenerator
from app.ai.prompts.cover_letter import build_cover_letter_prompt
from app.ai.providers.base import FakeLLMProvider
from app.ai.validator import CoverLetterValidator, clean_cover_letter_text
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


def test_validator_catches_instruction_leakage() -> None:
    result = CoverLetterValidator().validate(
        "Здравствуйте! Сделайте письмо живым, деловым, ATS-friendly, не длиннее 1700 символов."
    )

    assert result.valid is False
    assert any("service instruction leakage detected" in error for error in result.errors)


def test_clean_cover_letter_text_removes_instruction_leakage_line() -> None:
    text = clean_cover_letter_text(
        "\n".join(
            [
                "Здравствуйте! Хочу откликнуться на вакансию AI Backend Developer.",
                "Сделайте письмо живым, деловым, ATS-friendly, не длиннее 1700 символов.",
                "Буду рад пообщаться.",
            ]
        )
    )

    assert "Сделайте письмо" not in text
    assert "ATS-friendly" not in text
    assert "Хочу откликнуться" in text
    assert "Буду рад пообщаться" in text


def test_validator_keeps_normal_factual_letter_valid() -> None:
    result = CoverLetterValidator().validate(
        "Здравствуйте! Хочу откликнуться на вакансию Python Backend Developer.\n\n"
        "У меня есть опыт backend-разработки на Python: FastAPI, Flask, REST API, "
        "SQL/PostgreSQL, SQLAlchemy, Docker, Git, Linux.\n\n"
        "Буду рад пообщаться и подробнее рассказать о своём опыте."
    )

    assert result.valid is True


async def test_cover_letter_generator_uses_provider(vacancy, profile) -> None:
    provider = FakeLLMProvider("Здравствуйте! Хочу откликнуться на вакансию AI Backend Developer.")
    draft = await CoverLetterGenerator(provider).generate(vacancy, profile)

    assert draft.provider == "fake"
    assert draft.validation.valid is True
    assert provider.requests


async def test_cover_letter_generator_cleans_instruction_leakage(vacancy, profile) -> None:
    provider = FakeLLMProvider(
        "\n".join(
            [
                "Здравствуйте! Хочу откликнуться на вакансию AI Backend Developer.",
                "Сделайте письмо живым, деловым, ATS-friendly, не длиннее 1700 символов.",
            ]
        )
    )

    draft = await CoverLetterGenerator(provider).generate(vacancy, profile)

    assert "Сделайте письмо" not in draft.text
    assert "ATS-friendly" not in draft.text
    assert draft.validation.valid is True

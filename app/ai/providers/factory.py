from app.ai.providers.base import LLMProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import Settings


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(str(settings.ollama_base_url), settings.ollama_model)

    if not settings.openai_compatible_api_key or not settings.openai_compatible_model:
        raise ValueError("OpenAI-compatible provider requires API key and model")

    return OpenAICompatibleProvider(
        base_url=str(settings.openai_compatible_base_url),
        api_key=settings.openai_compatible_api_key,
        model=settings.openai_compatible_model,
    )


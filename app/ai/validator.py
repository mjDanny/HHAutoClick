import re
from dataclasses import dataclass, field

DEFAULT_GROWTH_ONLY_TECH = [
    "Kafka",
    "RabbitMQ",
    "Celery",
    "Kubernetes",
    "CI/CD",
    "observability",
    "ClickHouse",
    "MCP",
    "LangGraph",
    "PyTorch",
    "TensorFlow",
    "Keras",
    "OpenCV",
    "scikit-learn",
    "FinTech",
    "скоринг",
    "document parsing",
]

CONFIDENT_PATTERNS = [
    r"уверенно\s+владе[ею]",
    r"есть\s+опыт\s+(?:работы\s+)?с",
    r"работал[а]?\s+с",
    r"использовал[а]?\s+в\s+production",
    r"production[-\s]+опыт",
]

INSTRUCTION_LEAKAGE_PHRASES = [
    "сделайте письмо",
    "верните только",
    "не длиннее",
    "ats-friendly",
    "готовый текст письма",
    "без пояснений",
    "служебных инструкций",
]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class CoverLetterValidator:
    def __init__(self, growth_only_tech: list[str] | None = None, max_length: int = 1700) -> None:
        self.growth_only_tech = growth_only_tech or DEFAULT_GROWTH_ONLY_TECH
        self.max_length = max_length

    def validate(self, text: str) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if len(text) > self.max_length:
            errors.append(f"cover letter is too long: {len(text)} > {self.max_length}")

        if not text.strip().lower().startswith("здравствуйте"):
            warnings.append("cover letter should start with a greeting")

        lowered = text.lower()
        leaked_phrases = [
            phrase for phrase in INSTRUCTION_LEAKAGE_PHRASES if phrase in lowered
        ]
        if leaked_phrases:
            errors.append(
                "service instruction leakage detected: "
                + ", ".join(sorted(leaked_phrases))
            )

        for tech in self.growth_only_tech:
            tech_pattern = re.escape(tech.lower())
            has_tech = re.search(tech_pattern, lowered)
            if has_tech and self._has_confident_claim_near_tech(lowered, tech):
                errors.append(f"unsupported confident claim detected for {tech}")

        if re.search(r"\b\d+[%xх]\b|\b\d+\s+(?:лет|года|год)\b", lowered):
            warnings.append("numeric claims should be manually verified")

        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def _has_confident_claim_near_tech(self, lowered_text: str, tech: str) -> bool:
        tech_lower = tech.lower()
        tech_index = lowered_text.find(tech_lower)
        if tech_index == -1:
            return False

        window_start = max(0, tech_index - 80)
        window_end = min(len(lowered_text), tech_index + len(tech_lower) + 80)
        window = lowered_text[window_start:window_end]
        return any(re.search(pattern, window) for pattern in CONFIDENT_PATTERNS)


def clean_cover_letter_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lowered_line = line.lower()
        if any(phrase in lowered_line for phrase in INSTRUCTION_LEAKAGE_PHRASES):
            continue
        lines.append(line)
    return "\n".join(lines).strip()

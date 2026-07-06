from app.core.config import CandidateProfile
from app.hh.models import NormalizedVacancy

BASE_COVER_LETTER_TEMPLATE = """Здравствуйте! Хочу откликнуться на вакансию {title}.

У меня есть опыт backend-разработки на Python: FastAPI, Flask, REST API,
SQL/PostgreSQL, SQLAlchemy, Docker, Git, Linux.

Работал над backend-сервисами и API: разрабатывал серверную логику,
интеграции, обрабатывал пользовательские сценарии, дорабатывал существующий
функционал, исправлял баги и повышал стабильность backend-части.

[Адаптируй этот абзац под вакансию.]

Буду рад пообщаться и подробнее рассказать о своём опыте."""


def build_cover_letter_prompt(vacancy: NormalizedVacancy, profile: CandidateProfile) -> str:
    confirmed = ", ".join(profile.confirmed_skills)
    growth = ", ".join(profile.growth_skills)
    contacts = ", ".join(
        item for item in [profile.contacts.telegram, profile.contacts.email] if item
    )
    key_skills = ", ".join(vacancy.key_skills) or "not specified"

    return f"""
Ты помогаешь написать короткое сопроводительное письмо на русском для hh.ru.

Позиционирование кандидата: {profile.position}
Контакты кандидата: {contacts or "не добавлять, если не нужно"}

Подтвержденный опыт кандидата:
{confirmed}

Технологии только для честной формулировки интереса или готовности быстро погрузиться:
{growth}

Запрещено:
- выдумывать компании, годы, цифры, достижения и production experience;
- писать, что кандидат уверенно владеет технологиями из списка growth-only;
- автоматически отвечать на вопросы работодателя или тестовые задания;
- использовать фальшивые HR-клише.

Вакансия:
Название: {vacancy.title}
Компания: {vacancy.company or "не указана"}
Ключевые навыки: {key_skills}
Описание: {vacancy.description[:3000]}

Базовый формат:
{BASE_COVER_LETTER_TEMPLATE.format(title=vacancy.title)}

Сделай письмо живым, деловым, ATS-friendly, не длиннее 1700 символов.
Используй ключевые слова из вакансии, но не превращай письмо в набор тегов.
Если вакансия требует неподтвержденную технологию, формулируй честно:
"готов быстро погрузиться в рабочем контексте" или "интересно развиваться в этом направлении".
""".strip()

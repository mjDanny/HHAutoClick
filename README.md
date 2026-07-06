# Personal HH Job Autopilot

Личный ассистент для поиска вакансий на hh.ru, оценки релевантности, генерации сопроводительных писем и ручного подтверждения откликов.

MVP намеренно построен вокруг безопасного режима review-first: `AUTO_APPLY_ENABLED=false` и `DRY_RUN=true` по умолчанию. Проект не обходит CAPTCHA, антибот-защиты, fingerprinting, лимиты платформы и не отправляет ответы на вопросы работодателя без явного подтверждения.

## Что уже есть

- модульная структура FastAPI + сервисы + Telegram skeleton + Playwright skeleton;
- официальный hh.ru API client для поиска и получения вакансий;
- foundation для отдельного Playwright persistent browser profile;
- нормализация вакансий;
- rule-based scoring под профиль Python Backend / AI Backend Developer;
- абстракция LLM-провайдера: Ollama и OpenAI-compatible API;
- генератор промпта и сопроводительного письма;
- validator против выдумывания неподтверждённых технологий;
- SQLite/SQLAlchemy модели и репозитории для истории вакансий и откликов;
- blacklist, duplicate guard, dry-run и rate-limit настройки;
- тесты ключевой доменной логики.

## Быстрый старт

```bash
python3.11 -m venv venv
./venv/bin/pip install -e ".[dev]"
cp .env.example .env
cp configs/profile.example.yaml configs/profile.yaml
cp configs/searches.example.yaml configs/searches.yaml
./venv/bin/python -m uvicorn app.main:create_app --factory --reload
```

Проверка здоровья:

```bash
curl http://127.0.0.1:8000/health
```

## Тесты и проверки

```bash
./venv/bin/python -m ruff check .
./venv/bin/python -m pytest
./venv/bin/python -m mypy app tests
./venv/bin/python -c "from app.main import create_app; app = create_app(); print(app.title)"
```

## Конфигурация

Все секреты хранятся только в `.env`, который не должен попадать в git. Примеры лежат в `.env.example`, `configs/profile.example.yaml` и `configs/searches.example.yaml`.

Ключевые флаги:

- `AUTO_APPLY_ENABLED=false` - ручное подтверждение откликов;
- `DRY_RUN=true` - не выполнять действия отправки;
- `LLM_PROVIDER=ollama` или `LLM_PROVIDER=openai_compatible`;
- `USE_BROWSER_PROFILE=true` - MVP authenticated/review flow через отдельный профиль;
- `BROWSER_PROFILE_DIR=.local/browser-profile` - не основной браузер пользователя;
- `BROWSER_HEADLESS=false` - видимый браузер для ручного логина;
- `USE_OAUTH=false` - OAuth оставлен как будущий optional mode;
- `MAX_APPLICATIONS_PER_DAY` и `APPLICATION_COOLDOWN_SECONDS` ограничивают частоту откликов.

## Browser Profile Auth Mode

В MVP приложение не использует OAuth для авторизации hh.ru. Оно создаёт отдельный профиль браузера в `.local/browser-profile`, открывает видимый браузер, пользователь вручную логинится в hh.ru, а приложение проверяет авторизацию через `HH_LOGIN_CHECK_URL`.

Если обнаружены login page, CAPTCHA/challenge, вопросы работодателя или тестовое задание, сценарий останавливается и переходит в ручной review. Основной личный браузер пользователя по умолчанию не используется.

## Документация

- [Research report](docs/RESEARCH_REPORT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)

## Что не реализовано в первом проходе

- реальная отправка отклика на hh.ru;
- OAuth flow hh.ru для соискателя как optional/future mode;
- полноценный Telegram approval flow;
- web dashboard с HTMX;
- scheduler loop с persistent jobs;
- Alembic migrations;
- обработка реальных форм вопросов работодателя в браузере.

Следующий практичный шаг: реализовать read-only pipeline `search -> normalize -> score -> store -> show in API/Web`, затем подключить Telegram-кнопки review/skip/open.

# Personal HH Job Autopilot

Личный ассистент для поиска вакансий на hh.ru, оценки релевантности, генерации сопроводительных писем и ручного подтверждения откликов.

MVP намеренно построен вокруг безопасного режима review-first: `AUTO_APPLY_ENABLED=false` и `DRY_RUN=true` по умолчанию. Проект не обходит CAPTCHA, антибот-защиты, fingerprinting, лимиты платформы и не отправляет ответы на вопросы работодателя без явного подтверждения.

## Что уже есть

- модульная структура FastAPI + сервисы + Telegram skeleton + browser-profile слой;
- официальный hh.ru API client для поиска и получения вакансий;
- read-only pipeline: search config -> hh API -> normalize -> filter -> score -> store;
- JSON API и простой server-rendered dashboard для просмотра вакансий;
- локальный review workflow: skip, blacklist company, cover letter drafts and validation;
- отдельный Playwright persistent browser profile с login check и безопасным открытием вакансии;
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

Локальные рабочие конфиги создаются из examples и не коммитятся:

```bash
cp configs/profile.example.yaml configs/profile.yaml
cp configs/searches.example.yaml configs/searches.yaml
```

Если `configs/profile.yaml` или `configs/searches.yaml` отсутствуют, pipeline вернёт понятную ошибку с просьбой скопировать example-файлы.

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

Команды:

```bash
./venv/bin/python -m app.cli browser-login
./venv/bin/python -m app.cli browser-check-login
./venv/bin/python -m app.cli browser-open-vacancy <local-vacancy-id>
```

Web UI показывает состояние browser-profile login check на главной странице. На странице вакансии можно открыть сохранённую вакансию в отдельном профиле проекта. Эти действия не отправляют отклик.

## Read-only Pipeline

Pipeline не отправляет отклики. Он только ищет вакансии через официальный API hh.ru, получает детали, нормализует данные, применяет blacklist/dedupe, считает rule-based score и сохраняет результат в SQLite.

Запуск через API:

```bash
curl -X POST http://127.0.0.1:8000/api/pipeline/run-readonly
```

Dashboard:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/vacancies
```

Доступные endpoints:

- `GET /health`
- `POST /api/pipeline/run-readonly`
- `GET /api/vacancies`
- `GET /api/vacancies/{vacancy_id}`
- `GET /api/stats`
- `POST /api/vacancies/{vacancy_id}/skip`
- `POST /api/vacancies/{vacancy_id}/blacklist-company`
- `POST /api/vacancies/{vacancy_id}/cover-letter/generate`
- `POST /api/vacancies/{vacancy_id}/cover-letter/rewrite`
- `GET /api/vacancies/{vacancy_id}/cover-letters`
- `GET /api/blacklist`
- `POST /api/browser/check-login`
- `POST /api/browser/open-vacancy/{vacancy_id}`

`GET /api/vacancies` поддерживает `limit`, `offset`, `min_score`, `status`, `company`, `q`.

## Review Workflow

Все review-действия пока локальные: они меняют SQLite-состояние и не отправляют отклики на hh.ru.

На странице `http://127.0.0.1:8000/vacancies/{id}` можно:

- увидеть score, reasons и concerns;
- сгенерировать cover letter draft;
- переписать draft с дополнительной инструкцией;
- увидеть validation status и validation errors;
- пометить вакансию как `skipped`;
- добавить компанию в persistent blacklist.

Persistent company blacklist учитывается будущими read-only pipeline runs. Если новая вакансия приходит от blacklisted company, она сохраняется со статусом `blacklisted`, чтобы было видно, почему она не попала в обычный review.

Cover letter validation блокирует уверенные claims по неподтверждённым технологиям и сохраняет ошибки в базе. При невалидном draft вакансия получает статус `needs_manual_review`; при валидном draft - `draft_ready`.

## Документация

- [Research report](docs/RESEARCH_REPORT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)

## Что не реализовано в первом проходе

- реальная отправка отклика на hh.ru;
- полноценный Telegram approval flow;
- OAuth flow hh.ru для соискателя как optional/future mode;
- Alembic migrations перед долгим использованием существующей базы;
- scheduler loop с persistent jobs;
- сохранение содержимого реальных форм вопросов работодателя в браузере;
- реальное открытие apply URL и отправка отклика.

Следующий практичный шаг: manual apply draft flow поверх уже подготовленного browser-profile слоя.

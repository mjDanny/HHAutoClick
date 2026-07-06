# Research Report

Дата spike: 2026-07-06.

Цель: изучить публичные проекты вокруг hh.ru automation и официальную документацию hh.ru, не копируя код и не наследуя небезопасные практики.

## Источники

- Vlad9572324/hh.ru-clicker: https://github.com/Vlad9572324/hh.ru-clicker
- Steev193/hh-ru-apply: https://github.com/Steev193/hh-ru-apply
- semernyakov/hh-auto-apply: https://github.com/semernyakov/hh-auto-apply
- AgentShekel/hh-bot: https://github.com/AgentShekel/hh-bot
- kapturoff/pyhh: https://github.com/kapturoff/pyhh
- fikstt2/hh-ai-agent: https://github.com/fikstt2/hh-ai-agent
- s1rry/hh-avtootkliki: https://github.com/s1rry/hh-avtootkliki
- hhru/api: https://github.com/hhru/api
- hh.ru vacancies docs: https://github.com/hhru/api/blob/master/docs/vacancies.md
- hh.ru negotiations docs: https://github.com/hhru/api/blob/master/docs/negotiations.md

## Сводная таблица

| Проект | Стек | Работа с hh.ru | UI | LLM/scoring/letters | Safety/limits | Лицензия | Пригодность |
|---|---|---|---|---|---|---|---|
| Vlad9572324/hh.ru-clicker | Python, FastAPI, vanilla JS, Docker, pytest | Cookies, reverse-engineered endpoints, OAuth-compatible notes, WebSocket/chat endpoints | Web dashboard | LLM replies, questionnaire logic, rich analytics | Has limits, duplicate storage, tests; also contains aggressive automation ideas | No standard OSS license found; README says personal/use at own risk | Ideas only: dashboard, event log, storage, limit counters. Do not copy code. |
| Steev193/hh-ru-apply | Public page available, details sparse from GitHub preview | Appears to be hh apply automation | Unknown | Unknown | Unknown | Not confirmed | Low confidence; cite as checked but not a strong source. |
| semernyakov/hh-auto-apply | Repository page was not accessible during spike | Unknown | Unknown | Unknown | Unknown | Unknown | Not used beyond noting unavailability. |
| AgentShekel/hh-bot | Python, aiogram, Playwright, OpenAI-compatible LLM | Browser automation, manual login, cookies, hh vacancy URLs | Telegram | LLM score, cover letters, self-critique, score bands | Auto-apply off by default, manual middle band, blacklist, dedupe | License file exists, exact license not verified in preview | Good source of product-flow ideas; avoid direct code. |
| kapturoff/pyhh | FastAPI, SQLAlchemy, SQLite, Playwright, Ollama, Vue, Docker | Playwright via CDP to a user browser | Web + Telegram | Ollama scoring and detailed match | Pipeline state and restart continuation | MIT in README | Strong architecture ideas for MVP; UI stack is heavier than needed. |
| fikstt2/hh-ai-agent | Repository page not available during spike | Unknown | Unknown | Unknown | Unknown | Unknown | Not used. |
| s1rry/hh-avtootkliki | Python, aiogram, Playwright, SQLAlchemy/SQLite, APScheduler, Claude-compatible API | Direct API + Playwright + stored sessions | Telegram | Rule analyzer, cover letters, questions/tests | Has dedupe, skip failed, limits; includes anti-detect and AI test answering | No standard license confirmed | Use rule-scoring and data model ideas; reject anti-detect and test auto-answering. |
| hhru/api | Official API docs/OpenAPI | Official vacancies, negotiations, OAuth | None | None | Official auth and response semantics | Official documentation | Primary source for API boundaries. |

## Детальные наблюдения

### Vlad9572324/hh.ru-clicker

- Стек: Python 3.10+, FastAPI, uvicorn/aiohttp/requests, vanilla JS dashboard, Docker, pytest.
- hh.ru: cookies, reverse-engineered endpoints, `chatik.hh.ru`, websocket push, some OAuth-compatible paths.
- UI: dense web dashboard with event log, applications history, settings, raw config backup.
- LLM: OpenAI-compatible client, auto replies, questionnaire handling, robot button picker.
- Scoring: more analytics/reply-oriented than clean candidate-fit scoring.
- Dry-run: not clearly central in README preview.
- Auto-apply: core feature.
- Limits: counters, HH limit ETA, auto-pause on errors/limits.
- Blacklist/duplicates: discard filters, applied storage, duplicate prevention.
- Tests/Docker: README mentions 138+ tests and Docker.
- Risks: reverse-engineered/private endpoints, cookie handling, questionnaire automation, high automation surface.
- Decision: take ideas for dashboard observability, redacted logs, duplicate storage, rate counters. Do not take reverse-engineered private calls, cookie import flows, questionnaire auto-fill, or code.

### Steev193/hh-ru-apply

- Public page opened but preview did not expose enough README details.
- License, tests, Docker, exact approach: not confirmed.
- Decision: not used as a design source beyond noting it exists.

### semernyakov/hh-auto-apply

- Repository was not accessible from public browsing during the spike.
- Decision: no architectural conclusions.

### AgentShekel/hh-bot

- Стек: Python, aiogram, Playwright, OpenAI-compatible Chat Completions providers.
- hh.ru: Playwright search, manual visible login, stored cookies, vacancy URL ingestion.
- UI: Telegram bot with buttons Apply/Skip/Open, periodic summary.
- LLM/scoring: score bands, cover letter generation, profile files, self-critique for fabricated facts and bad tone.
- Dry-run/auto-apply: `AUTO_APPLY_ENABLED=false` by default in README; high score can auto-apply only when explicitly enabled.
- Limits/blacklist/dedupe: title/company blacklist, employer rating floor, remote filter, cross-city dedupe, refusal to double apply.
- Risks: cookie storage and browser automation are sensitive; proxy mention exists.
- Decision: adopt review-first score routing, Telegram approval flow, prompt isolation, anti-fabrication validation. Keep provider abstraction cleaner and avoid platform-bypass features.

### kapturoff/pyhh

- Стек: FastAPI, SQLAlchemy, SQLite, Playwright, Ollama, httpx, Vue, Docker Compose, nginx.
- hh.ru: Playwright connects to an already logged-in browser via CDP; app does not perform auth itself.
- UI: Web app and Telegram notifications.
- LLM/scoring: Ollama scores vacancy 0-100, chooses resume, detailed match.
- Pipeline: parsing -> scoring -> filtering -> resume match -> detailed analysis -> Telegram; unfinished vacancies continue after restart.
- License: README says MIT.
- Risks: CDP and parsing require user browser hygiene; frontend stack heavier than requested for our MVP.
- Decision: take pipeline shape, local Ollama option, persisted pipeline state. Use server-rendered/HTMX later instead of Vue.

### s1rry/hh-avtootkliki

- Стек: Python, aiogram, Playwright, SQLAlchemy/SQLite, APScheduler, Claude-compatible API.
- hh.ru: direct API plus Playwright for login/chats/resume bump, browser sessions.
- UI: Telegram bot commands and callbacks.
- LLM/scoring: rule analyzer before AI, cover letters, recruiter messages, employer-question logic.
- Dry-run/auto-apply: auto-apply is a central worker; test apply command exists.
- Limits: max applies per day, delays, skip failed after repeated failures.
- Blacklist/duplicates: pre-sync of already sent applications, active vacancy list, failed skip.
- Tests/Docker: not confirmed from preview.
- Major risks: README references anti-detect Chromium, user-agent rotation, automatic test/question answering.
- Decision: accept rule-analyzer and skip-failed ideas; explicitly reject anti-detect, stealth, auto-answering tests, password login automation, high daily limits.

## Official hh.ru API notes

- `hhru/api` is the primary source for official capabilities.
- Vacancy search and vacancy detail are available via OpenAPI links from `docs/vacancies.md`.
- Short vacancy representation includes `id`, `name`, `alternate_url`, `apply_alternate_url`, `has_test`, `response_letter_required`, `employer`, `salary`, `area`, `experience`, `employment`.
- Applicant negotiations docs describe response/invitation entities and include "Откликнуться на вакансию", message list and sending/editing messages via official OpenAPI references.
- OAuth remains the official future option for authenticated applicant actions.
- For this MVP, authenticated review/apply preparation uses a separate visible Playwright persistent browser profile with manual user login.

## Architecture ideas to keep

- Review-first pipeline with explicit score bands.
- Rule-based pre-score before any LLM call to save tokens and improve explainability.
- LLM prompt must include confirmed skills and explicit negative list.
- Validator must reject fabricated confident claims.
- Store every vacancy/application decision with status and reason.
- Dedupe by hh vacancy id first, then canonical URL/title+company fallback.
- Telegram approval cards: Apply, Rewrite, Skip, Open on hh.ru.
- Stop on CAPTCHA, login page, ambiguous employer questions, tests, or form changes.
- Daily limits, cooldowns, and dry-run as first-class settings.

## Architecture ideas to reject

- CAPTCHA bypass, anti-detect browsers, fingerprint spoofing, proxy rotation for stealth.
- Automatic employer test completion.
- Unbounded auto-apply.
- Storing raw cookies/tokens in repository.
- Reverse-engineered private endpoints as MVP foundation.
- Large SPA frontend for first iteration.

## Licensing decision

No code is copied from researched projects. Projects without verified permissive licenses are used only as product/architecture references. For `kapturoff/pyhh`, README indicates MIT, but this project still only borrows high-level ideas. Official hh.ru docs are used as behavioral/API references.

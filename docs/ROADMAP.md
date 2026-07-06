# Roadmap

## Phase 0 - Done in first pass

- Research spike and architecture docs.
- Project skeleton.
- Pydantic settings.
- SQLAlchemy models and repositories.
- hh vacancy normalizer.
- Blacklist and duplicate filters.
- LLM provider abstraction with Ollama and OpenAI-compatible implementations.
- Rule-based vacancy scorer.
- Cover letter prompt builder, generator, and validator.
- Minimal FastAPI app.
- Minimal Telegram and Playwright skeletons.
- Docker and Docker Compose.
- Unit tests for pure domain logic.

## Phase 1 - Read-only pipeline

- Load `profile.yaml` and `searches.yaml`. Done.
- Call official hh.ru API: `GET /vacancies` and `GET /vacancies/{id}`. Done.
- Store normalized vacancies. Done.
- Score all new vacancies. Done.
- Add `/api/vacancies`, `/api/vacancies/{id}`, `/api/stats`. Done.
- Add `/vacancies` and `/vacancies/{id}` web pages with server-rendered templates. Done.
- Add Telegram notifications without sending actions.
- Generate cover letters only for review-threshold vacancies.

## Phase 2 - Review workflow

- Telegram buttons: Apply, Rewrite, Skip, Blacklist, Open.
- Web dashboard with the same decisions.
- Persist decision history and all generated drafts.
- Add manual letter edit endpoint.
- Add validation status and validation error display.

## Phase 3 - Playwright persistent profile

- Use `.local/browser-profile` as a separate project browser profile.
- First run opens visible browser; user logs in manually to hh.ru.
- Add `HH_LOGIN_CHECK_URL` login check.
- Open vacancy and apply URLs in the project profile.
- Detect login/CAPTCHA/challenge and mark `needs_manual_review`.
- Detect employer questions/test tasks and save them for review.
- Prepare manual apply draft flow without real sending.
- Keep `DRY_RUN=true` default.

## Phase 4 - Optional OAuth mode

- Implement official hh.ru OAuth as optional mode.
- Use official response/negotiation endpoints where available.
- Keep browser-profile mode available for manual review.
- Add strict preflight checks and daily limit/cooldown tests before any sending.

## Phase 5 - Limited auto-apply

- Require explicit `AUTO_APPLY_ENABLED=true`.
- Require successful manual testing of the browser-profile or OAuth flow.
- Allow only high-score vacancies with no tests/questions and a valid letter.
- Add audit log and emergency pause.
- Add metrics on sent/skipped/blocked actions.

## Phase 6 - Hardening

- Alembic migrations.
- Better scheduler persistence.
- More integration tests with mocked hh API and LLM.
- Structured JSON logs with secret redaction.
- Backup/export of local history without secrets.

# Architecture

## Principles

- Manual review is the default product mode.
- `AUTO_APPLY_ENABLED=false` and `DRY_RUN=true` by default.
- Official hh.ru API is the MVP read path for search and vacancy details.
- MVP authenticated/review/apply flow uses a separate Playwright persistent browser profile.
- Official OAuth mode is optional future work for more stable authenticated actions.
- Playwright is limited to visible user flows and detection of unsafe UI states.
- No CAPTCHA bypass, anti-detect, fingerprint spoofing, proxy rotation, hidden automation, or automatic employer-test completion.
- LLM output is treated as a draft and validated before being shown or sent.

## Modules

- `app/core`: settings, logging, typed exceptions.
- `app/hh`: official hh API client, domain models, vacancy normalizer, blacklist and duplicate filters.
- `app/ai`: LLM provider interface, Ollama/OpenAI-compatible providers, scorer, prompt builder, cover letter generator, validator.
- `app/storage`: SQLAlchemy engine/session, ORM models, repositories.
- `app/browser`: Playwright manager and session guard for explicit browser scenarios.
- `app/bot`: aiogram skeleton, approval keyboards and handlers.
- `app/api`: FastAPI routes and schemas.
- `app/services`: vacancy pipeline, application pipeline, scheduler boundary.

## Data Flow

1. Scheduler or user action starts a search using `searches.yaml`.
2. `HHApiClient` calls official vacancy search/detail endpoints.
3. `normalizer` converts raw hh JSON to `NormalizedVacancy`.
4. `BlacklistFilter` and `DuplicateGuard` skip blocked or already-known vacancies.
5. `RuleBasedVacancyScorer` assigns a transparent baseline score and reasons.
6. If score is high enough for review, `CoverLetterGenerator` builds a prompt and asks the configured LLM provider for a draft.
7. `CoverLetterValidator` checks for unsupported confident claims and style/length guardrails.
8. Vacancy, score, generated draft, validation status, and decision state are stored in SQLite.
9. Telegram/Web UI shows the vacancy card and draft.
10. User chooses Apply, Rewrite, Skip, Blacklist, or Open.
11. `ApplicationPipeline` opens review/apply pages through the project browser profile.
12. Real sending is not implemented in the current foundation; future sending requires manual approval unless explicit safe auto-apply criteria are met.

## hh.ru API Usage

MVP read path:

- `GET /vacancies` for search.
- `GET /vacancies/{id}` for detail.

The API client sets a clear `HH_USER_AGENT`, supports optional bearer token for future OAuth mode, and logs HTTP errors without secrets.

Authenticated actions are not based on OAuth in the MVP. Official OAuth mode remains a future optional path for response/negotiation endpoints when stability and account permissions justify it.

## Browser Profile Auth Mode

MVP authentication uses a separate Playwright persistent browser profile:

- `BROWSER_PROFILE_DIR=.local/browser-profile`;
- `BROWSER_HEADLESS=false` by default, so the user can see and control login;
- `BROWSER_CHANNEL=chromium` by default, with `chrome` allowed when installed;
- `USE_BROWSER_PROFILE=true`;
- `USE_OAUTH=false`.

First run:

1. App creates the browser profile directory if needed.
2. App opens a visible browser context using only this project profile.
3. User manually logs in to hh.ru in the browser.
4. App checks `HH_LOGIN_CHECK_URL=https://hh.ru/applicant/resumes`.
5. If the check page is safe and not a login/challenge page, the profile is considered authenticated.

The app does not connect to the user's main personal browser by default. It does not touch personal tabs, cookies, history, or existing browser profiles outside the project profile directory.

Implemented entry points:

- CLI: `browser-login`, `browser-check-login`, `browser-open-vacancy <local-vacancy-id>`;
- API: `POST /api/browser/check-login`, `POST /api/browser/open-vacancy/{vacancy_id}`;
- Web UI: login check on the index page and “Open in browser profile” on a vacancy page.

The current implementation opens saved vacancy URLs and checks page state. It does not submit applications and does not fill employer forms.

## Playwright Usage

Playwright is not the primary API layer. It is reserved for:

- opening a vacancy/application page for user review;
- checking whether the project browser profile is still logged in;
- detecting CAPTCHA or unexpected challenge pages;
- detecting employer questions/tests/forms when official API data is insufficient.

Browser detection states are conservative: `logged_in`, `logged_out`, `captcha`, `challenge`, `ok`, `login_required`, `employer_questions`, `test_task`, and `unknown`.

On CAPTCHA, challenge, login page, blocked page, unexpected form structure, employer questions, test tasks, or unknown state, browser automation stops and records `needs_manual_review` where a vacancy is involved.

No CAPTCHA bypass, anti-detect browser, proxy rotation, fingerprint spoofing, or hidden automation is implemented or planned for MVP.

## Optional OAuth Mode

`USE_OAUTH=false` in MVP. OAuth is kept as a future official mode for authenticated actions:

- applicant authorization through official hh.ru OAuth;
- response/negotiation endpoints where available;
- less dependence on browser DOM changes.

OAuth mode must not block read-only API search or browser-profile manual review in the MVP.

## LLM Scoring

MVP includes rule-based scoring first. LLM scoring can be added as a second pass:

- input: normalized vacancy, candidate profile summary, confirmed skills, growth-only skills, blacklist context;
- output: score 0-100, reasons, matched skills, concerns, recommendation;
- parser must reject malformed LLM JSON and fall back to rule score.

Rule score remains stored for auditability.

## Cover Letter Generation

`build_cover_letter_prompt` provides:

- vacancy title/company/description/key skills;
- candidate confirmed skills;
- technologies that must not be claimed as confident experience;
- required Russian business style;
- base format requested for hh.ru;
- instruction to use growth-only wording for unconfirmed technologies.

The generator accepts any `LLMProvider`, so Ollama and OpenAI-compatible APIs are interchangeable.

## Cover Letter Validation

`CoverLetterValidator` checks:

- unsupported technologies used with confident-experience phrasing;
- false achievements/numbers markers when unsupported by the profile;
- excessive length;
- missing greeting;
- optional contact presence.

Invalid drafts are stored but not sent. UI must show validation errors and request rewrite or manual edit.

## Telegram Approval Flow

Default flow:

- bot posts vacancy card with score, reasons, salary, company, URL, and generated letter;
- buttons: `Apply`, `Rewrite`, `Skip`, `Blacklist company`, `Open on hh.ru`;
- `Apply` opens a visible browser-profile flow only for a stored vacancy and approved letter;
- if employer questions/test/CAPTCHA/login are detected, bot shows the issue and does not send;
- rewrite creates a new draft and keeps old drafts in history.

## Storage

SQLite stores:

- vacancies with `hh_id`, canonical URL, title, company, salary, raw payload hash, and flags;
- vacancy scores with score, reasons, matched skills, concerns;
- cover letters with prompt, draft, provider, validation result;
- applications with status, dry-run flag, decision source, sent/approved timestamps;
- blacklist entries for title/company/vacancy terms;
- events for audit logs.

## Blacklist

Blacklist checks run before LLM calls:

- title terms;
- company terms;
- vacancy ids;
- future: domain-specific rules.

Matches are stored as skip reasons so skipped vacancies are explainable.

## Duplicate Prevention

Dedupe order:

1. exact `hh_id`;
2. canonical vacancy URL without tracking params;
3. normalized `(title, company)` fallback.

Repository writes should enforce uniqueness where possible, and application sending checks both vacancy and application tables.

## Rate Limits

Configuration:

- `MAX_APPLICATIONS_PER_DAY`;
- `APPLICATION_COOLDOWN_SECONDS`;
- per-search page limits;
- future per-endpoint API limiter.

When a limit is hit, the pipeline records `rate_limited` and schedules/manual UI can retry later.

## Dry-run

`DRY_RUN=true` means the system can search, score, generate letters, validate, store, and show UI actions, but application sending returns a simulated result. This is the required mode for first real tests.

## Auto-apply Safety

Auto-apply may run only if all conditions are true:

- `AUTO_APPLY_ENABLED=true`;
- `DRY_RUN=false`;
- browser-profile flow has been manually tested for the current account;
- score >= `MIN_SCORE_FOR_AUTO_APPLY`;
- no employer questions;
- no test task;
- no CAPTCHA/login/challenge;
- valid cover letter;
- no duplicate application;
- daily limit and cooldown allow it.

Any ambiguity routes to manual review.

## Error Handling

- API/network errors: retry later with bounded attempts, store event.
- LLM errors: keep vacancy, mark letter generation failed, allow manual retry.
- Validation errors: store draft, block sending.
- CAPTCHA/login/challenge: stop browser scenario, notify user.
- Employer questions/tests: save detected form/question text and show manual approval workflow.
- Unexpected DOM/API schema: stop the specific action and log structured context without secrets.

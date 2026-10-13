# Mori backend development

This directory contains the Python 3.13 backend package. Identity, user, learner
profiles, the code-backed curriculum catalog, access, and sessions are modules in one
FastAPI application.
Sign-in links Google identity, updates the application account, and issues the intro grant in
one transaction. Profile onboarding confirms the selected languages and preferences separately.
The session foundation adds idempotent intro-grant reservation and an immutable,
versioned learning plan. A pure prompt compiler loads that pinned plan, validates
its course and policy versions, and builds server-only tutor instructions.

When `OPENAI_EXTRACTOR_MODEL` is set, usable finalized sessions atomically enqueue
an analysis job. A separate Procrastinate worker extracts a brief structured recap,
one to three transcript-cited learnings about lesson practice, and specific volunteered
interests or occupations. Accepted insights enter the editable Learner File for up to
90 days and can personalize later calls. Analysis does not yet update lesson passage,
level, or a planning snapshot.

Learning extraction receives the selected languages and full pinned lesson guidance.
Observations preserve exact learner quote spans, optional preceding tutor opportunities,
and assistance labels. A separate semantic review checks whether the full transcript
supports each claim; unsupported or uncertain observations are omitted. A failed or
incomplete review leaves analysis retryable without a partial capture commit. This adds
one request using the configured extraction model when learning observations are present.
Both requests disable provider storage; Fluent sessions do not run evidence review.
Migration `20261012_0015` adds the evidence fields and keeps existing observations as
legacy records. Apply migrations before starting the updated API or analysis worker.

Run the worker in another terminal:

```sh
uv run --directory apps/backend procrastinate --app mori.modules.learning.queue.app worker --queues analysis
```

Keep `OPENAI_EXTRACTOR_MODEL` empty until a model passes transcript evaluation. With
no configured model, voice sessions can still end, but recap status is unavailable.

Realtime bootstrap persists a call attempt and prompt-build manifest before a provider
request. The API exchanges SDP server-side, and an asyncio supervisor owns each call
through a renewable PostgreSQL lease. It persists an absolute deadline, hangs up
expired or ended calls, and stores finalized transcript turns. Browser acknowledgement
waits for the server sideband stream. A second API process can claim an expired lease
after process loss; a gap in the transcript marks analysis as failed. The webapp enables
voice only when the supervisor reports healthy. A real provider call and process-loss
drill remain to be verified before treating this as the complete M2 gate.

If call creation has no definite result, setup fails and the intro reservation is
released because no SDP answer was returned to the browser. The attempt remains
`ambiguous` for provider reconciliation. A late call ID moves it to `cleanup_pending`;
the supervisor retries hangup until it succeeds. Without a call ID, the supervisor
marks the attempt ended after two hours, beyond OpenAI's documented 60-minute
Realtime session limit. The create-call request carries the attempt ID as
`X-Client-Request-Id` for investigation. A learner can create another session, but
three recent unidentified calls or uncleaned known calls temporarily block further
voice setup. A late definitive rejection resolves an ambiguous attempt as
`provider_failed`.
If `cleanup_pending` persists, inspect the stored `provider_call_id` and provider
request ID. Resolve the attempt only after provider hangup or expiry is verified;
the learner's reservation has already been released.

Mori's language-independent ten-lesson sequence and conversation guidance live in
`src/mori/modules/curriculum/curriculum.py`. The catalog exposes one course for
all supported target languages. The compiler uses one shared tutor prompt for
all lessons and languages. Beginner treats basic greetings, name/origin introductions,
and common short phrases as familiar. Lesson 1 builds beyond them into daily life,
opening with a connected question before teaching or modelling an answer. New call
builds use `mori-framework-v4`, including compatible v2/v3 saved plans; the build
manifest records the resolved policy. Older unsupported engines remain history-only.
Create a new session to try it. Migration 0005 still converts historical course references
to stable item keys.

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop or another Docker-compatible runtime with Compose v2

## First-time setup

From the repository root:

```sh
cp .env.example .env
uv sync --directory apps/backend --locked
docker compose up -d postgres
docker compose ps
```

The PostgreSQL health status should become `healthy`. The database is available only on the local loopback interface at `localhost:5432` by default.

Check the database directly through the container:

```sh
docker compose exec postgres pg_isready -U mori -d mori
docker compose exec postgres psql -U mori -d mori -c 'select version();'
```

Stop the service without deleting its data:

```sh
docker compose stop postgres
```

`docker compose down --volumes` deletes the local database volume. Use it only when a full local reset is intended.

## Environment variables

Copy the root `.env.example` to the ignored root `.env`. Local PostgreSQL values are development-only defaults and are not production credentials.

### Google OIDC

| Variable | Source | Local value or requirement |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | Google Cloud OAuth client | Client ID for the development Web application client |
| `GOOGLE_CLIENT_SECRET` | Google Cloud OAuth client | Client secret for the same development client |
| `GOOGLE_REDIRECT_URI` | Mori configuration | `http://localhost:8000/auth/google/callback` |
| `SESSION_SIGNING_KEY` | Generate locally | Independent random 32-byte or longer secret |
| `OAUTH_STATE_KEY` | Generate locally | Independent random 32-byte or longer secret |

Generate each Mori-owned secret separately:

```sh
openssl rand -hex 32
```

The Google client must register the redirect URI exactly, including scheme, port, path, and lack of a trailing slash. Request only `openid`, `email`, and `profile` scopes for sign-in.

### OpenAI

| Variable | Source | Local value or requirement |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI development project | Project-scoped API key used by the server Realtime adapter. |
| `OPENAI_REALTIME_MODEL` | Mori configuration | Defaults to `gpt-realtime-2.1`; pin or change after live evaluation. |
| `OPENAI_REALTIME_VOICE` | Mori configuration | Defaults to `marin`. |
| `OPENAI_EXTRACTOR_MODEL` | Mori configuration | Leave empty until the extraction evaluation selects a model; then start the analysis worker. |
| `OPENAI_SAFETY_ID_SECRET` | Generate locally | Independent random 32-byte or longer secret used to derive privacy-preserving safety identifiers. |

The model and safety variables are Mori configuration, not values issued by OpenAI. A project-scoped API key does not require an additional organization or project ID variable for the initial integration.

Never expose these variables to Vite or prefix them with `VITE_`. All provider calls and secret handling belong to the backend.
Both `OPENAI_API_KEY` and `OPENAI_SAFETY_ID_SECRET` must be set before the voice
availability endpoint enables calls. All environments use a 10-minute absolute
server cap.

## Dependency workflow

Run uv commands from the repository root with `--directory apps/backend`, or run them directly inside `apps/backend`.

```sh
uv sync --directory apps/backend --locked
uv run --directory apps/backend pytest
```

Commit `pyproject.toml` and `uv.lock`. Do not commit `.env` or `.venv`.

## Database and API

Apply migrations explicitly before starting the API:

```sh
uv run --directory apps/backend alembic upgrade head
uv run --directory apps/backend uvicorn mori.api.main:create_app --factory --reload --no-access-log
```

Migration 0009 adds learning-intent fields. A database with existing profiles must
upgrade to `20261006_0009`, backfill each profile's goal and speaking context with
accurate learner-provided values, then upgrade to head. Migration 0010 checks that
no fields are blank before enforcing non-null constraints. New profiles must supply
these answers during onboarding; optional notes are stored as an empty string.

The API listens on `http://localhost:8000` by default. Liveness is available at `/health`,
database readiness at `/ready`, and development OpenAPI documentation at `/docs`.

## API contract generation

The FastAPI application exports the checked-in OpenAPI contract without connecting to a database
or reading local credentials. Run these commands after changing public routes or Pydantic schemas:

```sh
uv run --directory apps/backend python scripts/export_openapi.py
npm --prefix packages/api-client run generate
```

`packages/api-client` contains the generated TypeScript SDK, response types, and Zod validators.
The web gateway uses its generated `GET /me` response validator. CI checks both the OpenAPI
export and generated files for drift, then builds and tests the web consumer. New sign-ins return
an incomplete learner with no profile. `POST /api/v1/language-profiles` confirms supported languages,
starting mode, and preferences in one idempotent transaction before session creation is allowed.

The initial identity endpoints are:

- `GET /auth/google/start`
- `GET /auth/google/callback`
- `POST /auth/logout`
- `GET /api/v1/me`
- `PATCH /api/v1/me/preferences`
- `POST /api/v1/sessions` with `Idempotency-Key`, origin, CSRF token, and
  `{"languageProfileId":"<active profile UUID>"}`
- `GET /api/v1/sessions/{id}` for the learner's authoritative session status

See [the identity contract](../../docs/architecture/identity-contract.md) for session,
callback, CSRF, cookie, and optimistic-concurrency behavior.

## Verification

An opt-in evaluator checks generated openings and one follow-up with synthetic
learner context using the configured Realtime model and API key. It makes provider
requests without creating app sessions or consuming learner grants. These are
transcript checks; audio output does not evaluate acoustic quality or browser delivery.

```sh
uv run --directory apps/backend python scripts/evaluate_tutor_openings.py --trials 2 --output ../../.codex/tutor-opening-evaluation.json
uv run --directory apps/backend python scripts/evaluate_tutor_openings.py --trials 2 --modality audio --scenario returning_introduction --output ../../.codex/tutor-opening-audio-evaluation.json
```

Run the complete backend gate from the repository root:

```sh
uv run --directory apps/backend ruff check src tests migrations
uv run --directory apps/backend mypy
uv run --directory apps/backend pytest
uv run --directory apps/backend alembic check
```

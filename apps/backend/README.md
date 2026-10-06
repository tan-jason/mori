# Mori backend development

This directory contains the Python 3.13 backend package. Identity, user, learner
profiles, the code-backed curriculum catalog, access, and sessions are modules in one
FastAPI application.
Sign-in links Google identity, updates the application account, and issues the intro grant in
one transaction. Profile onboarding confirms the selected languages and preferences separately.
The session foundation adds idempotent intro-grant reservation and an immutable,
versioned learning plan. A pure prompt compiler loads that pinned plan, validates
its course and policy versions, and builds server-only tutor instructions.

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
all lessons and languages. The first Beginner lesson starts mostly in the
learner's base language and guides a personal introduction without a fixed question
script. Create a new session to try it. Plans pinned to the retired prompt engine
cannot start a new call. Migration 0005 still converts historical course references
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
| `OPENAI_EXTRACTOR_MODEL` | Mori configuration | Leave empty until the extraction evaluation selects a model. |
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

Run the complete backend gate from the repository root:

```sh
uv run --directory apps/backend ruff check src tests migrations
uv run --directory apps/backend mypy
uv run --directory apps/backend pytest
uv run --directory apps/backend alembic check
```

# Mori backend development

This directory contains the Python 3.13 backend package. The current scaffold establishes the uv toolchain and local PostgreSQL dependency. API and application modules will be added during M1.

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
| `OPENAI_API_KEY` | OpenAI development project | Project-scoped API key. This is the standard variable read by the OpenAI SDK. |
| `OPENAI_REALTIME_MODEL` | Mori configuration | Leave empty until the realtime evaluation selects a model. |
| `OPENAI_EXTRACTOR_MODEL` | Mori configuration | Leave empty until the extraction evaluation selects a model. |
| `OPENAI_SAFETY_ID_SECRET` | Generate locally | Independent random 32-byte or longer secret used to derive privacy-preserving safety identifiers. |

The model and safety variables are Mori configuration, not values issued by OpenAI. A project-scoped API key does not require an additional organization or project ID variable for the initial integration.

Never expose these variables to Vite or prefix them with `VITE_`. All provider calls and secret handling belong to the backend.

## Dependency workflow

Run uv commands from the repository root with `--directory apps/backend`, or run them directly inside `apps/backend`.

```sh
uv sync --directory apps/backend --locked
uv run --directory apps/backend pytest
```

Commit `pyproject.toml` and `uv.lock`. Do not commit `.env` or `.venv`.

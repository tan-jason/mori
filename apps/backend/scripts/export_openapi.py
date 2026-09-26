"""Export the public API contract without reading local credentials or contacting services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mori.api.main import create_app
from mori.config import Environment, Settings

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "packages/api-client/openapi.json"


def render_openapi() -> str:
    settings = Settings(
        _env_file=None,
        MORI_ENV=Environment.TEST,
        API_ORIGIN="http://testserver",
        WEB_ORIGIN="http://web.test",
        DATABASE_URL="postgresql+psycopg://mori:mori@localhost/mori",
        GOOGLE_CLIENT_ID="contract-export",
        GOOGLE_CLIENT_SECRET="contract-export",
        GOOGLE_REDIRECT_URI="http://testserver/auth/google/callback",
        SESSION_SIGNING_KEY="contract-export-key-at-least-32-characters",
        OAUTH_STATE_KEY="contract-export-state-at-least-32-characters",
    )
    return json.dumps(create_app(settings=settings).openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed export differs")
    args = parser.parse_args()
    rendered = render_openapi()
    if args.check:
        if not CONTRACT_PATH.exists() or CONTRACT_PATH.read_text() != rendered:
            parser.exit(1, "OpenAPI drift: regenerate packages/api-client/openapi.json\n")
        return 0
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

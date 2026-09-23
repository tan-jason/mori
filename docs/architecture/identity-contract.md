# Identity contract

**Status:** Initial implementation contract

**Scope:** Google sign-in, Mori application sessions, learner identity, the default
English-to-Mandarin profile, preferences, consent history, and the introductory grant.

## Authentication flow

1. `GET /auth/google/start` creates a single-use database login attempt and redirects to
   Google using authorization code flow, PKCE S256, state, and nonce. A short-lived,
   HttpOnly cookie binds that state to the browser that initiated the flow.
2. `GET /auth/google/callback` atomically consumes the login attempt before exchanging the
   code. A failed or replayed callback cannot create an application session.
3. A verified Google subject is linked to exactly one Mori user. Email is never used as the
   external identity key.
4. Provisioning creates the user, default language profile, default preferences, and one
   introductory grant idempotently.
5. Mori creates a 256-bit random application session and sends it in a host-only cookie.
   Only a keyed digest of the token is stored in PostgreSQL.

Google access and refresh tokens are not retained. Login attempts expire after ten minutes.
Application sessions expire after thirty days and are revoked on logout or account lifecycle
actions.

PostgreSQL stores login attempts so every API instance shares the same transaction state and
the callback can enforce single use atomically. The initial MVP retains consumed and expired
attempts, along with expired or revoked application sessions; expiry and revocation are still
enforced on every read. Retention cleanup and public-endpoint rate limiting are operational
gates for the controlled beta, not requirements for this initial identity slice.

## Browser controls

- Production uses the `__Host-mori_session` cookie with `HttpOnly`, `Secure`,
  `SameSite=Lax`, and `Path=/`.
- Credentialed CORS allows only configured web origins.
- Every unsafe cookie-authenticated request requires the exact configured `Origin` and an
  `X-CSRF-Token` value bound to the application session.
- Auth, API, and error responses use `Cache-Control: no-store`.
- Login destinations are selected from a configuration allowlist. Arbitrary return URLs are
  rejected.

## Initial HTTP surface

| Method and path | Result |
| --- | --- |
| `GET /auth/google/start` | Starts Google OIDC and redirects. |
| `GET /auth/google/callback` | Verifies Google identity, provisions state, and sets the application cookie. |
| `POST /auth/logout` | Revokes the current session and clears the cookie. |
| `GET /api/v1/me` | Returns the user, onboarding state, active language profile, preferences, and a session-bound CSRF token. |
| `PATCH /api/v1/me/preferences` | Updates preferences when `If-Match` matches the current preference version. |
| `GET /health` | Process liveness. |
| `GET /ready` | Database readiness. |

Preference responses include an `ETag` containing the preference version. Missing
`If-Match` returns `428`; a stale value returns `412`.

## Errors

Errors use this envelope:

```json
{
  "error": {
    "code": "authentication_required",
    "message": "Authentication is required.",
    "requestId": "6e9ef4b4-b358-443f-a8bb-88c6eb86486c"
  }
}
```

Validation details, OAuth codes, tokens, cookies, and provider payloads are not returned or
logged.

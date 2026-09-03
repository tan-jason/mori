# API and security

Mori exposes one public backend host, `https://api.mori`. REST is the application contract and one SDP endpoint bootstraps direct browser-to-provider WebRTC. Internal runtimes are never internet-facing.

## Public entry points

| Caller | Entry point | First owner | Result |
| --- | --- | --- | --- |
| Browser navigation | `https://mori/` and versioned assets | CloudFront and private S3 | Loads the React shell. The API origin is public configuration and no provider secret is embedded in the bundle. |
| Browser authentication | `GET /auth/google/start` and `GET /auth/google/callback` | API identity module | Completes OIDC, provisions the application user idempotently, and establishes an opaque application session. |
| React `WebAppGateway` | `https://api.mori/api/v1/*` | API use case | Authenticates, validates origin and CSRF where required, runs one bounded use case, commits, and maps the result to the OpenAPI contract. |
| Browser WebRTC adapter | `POST /api/v1/sessions/{id}/webrtc` with `application/sdp` | API session orchestration | Checks ownership and reservation, exchanges SDP, persists call identity and deadline, and returns the SDP answer. Media then flows directly to OpenAI. |
| Stripe | `POST /webhooks/stripe` | API billing adapter | Verifies the untouched request body, deduplicates the provider event, and advances the internal subscription projection. |
| Committed database state | Supervisor lease scan and Procrastinate queue | Private runtimes | Wakes durable live-call or background workflows without a public endpoint. |

Static asset caching is allowed through versioned object names. API, auth callback, SDP, and webhook responses must be explicitly non-cacheable.

## HTTP contract rules

- Version application endpoints under `/api/v1`.
- Pydantic v2 request and response models are the server source of truth.
- Generate and commit OpenAPI, then generate the TypeScript client and Zod runtime validators used by the production `WebAppGateway`.
- Fail CI when generated contracts differ from committed artifacts.
- Keep transport models, frontend view models, domain models, and persistence entities distinct.
- Declare response models for every route and sanitize production validation errors.
- Use machine-readable error codes with stable HTTP semantics. M0 must freeze the error envelope before client generation.
- Require an `Idempotency-Key` for session creation and any later create operation that could double-consume money, entitlement, or provider resources.
- Use optimistic versions or ETags for user-edited records where last-write-wins would lose intent.
- Apply ownership checks inside the application use case, not only in route matching or frontend state.

## First backend surface

| Route | Responsibility | Correctness behavior |
| --- | --- | --- |
| `GET /api/v1/me` | Authenticated learner, onboarding state, preferences, and language profile | First valid sign-in provisions the user, default language profile, and intro grant idempotently. |
| `PATCH /api/v1/me/preferences` | Correction frequency, playback preference, captions, and timezone | Optimistic version or ETag prevents lost updates. |
| `GET /api/v1/dashboard` | Composite response matching `DashboardSnapshot` | One server-composed read model. Machine timestamps remain available independently of display labels. |
| `POST /api/v1/sessions` | Create an attempt, reserve entitlement, select objectives, and persist a plan | Requires `Idempotency-Key`. No external call occurs while an entitlement lock is held. |
| `POST /api/v1/sessions/{id}/webrtc` | Accept an SDP offer, create the provider call, store the call ID and deadline, and return the SDP answer | Only the owning learner with a `planned` session may call it. A session has at most one active call. |
| `PUT /api/v1/sessions/{id}/audio-consent` | Grant, revoke, or decline the versioned session-specific audio policy | No retained audio bytes or upload URLs exist before a recorded grant. Revocation denies subsequent access immediately. |
| `POST /api/v1/sessions/{id}/audio-uploads` | Create a bounded multipart upload | URLs bind the storage key, session, part number, expiry, content constraints, and total byte budget. |
| `POST /api/v1/audio-uploads/{upload_id}/complete` | Complete and verify the upload manifest | Verifies expected parts, checksum, format, size, and current consent before marking the asset complete. |
| `POST /api/v1/sessions/{id}/end` | Record an idempotent learner end request | Persists the request and wakes the supervisor. The supervisor hangs up, fixes the final watermark, and queues analysis when usable. |
| `GET /api/v1/sessions/{id}` | Return state, connected time, remaining cap, and recap readiness | Supports reconnect and polling without trusting a client timer. |
| `GET /api/v1/sessions/{id}/recap` | Return the recap view model | Returns an explicit processing or failed state until current analysis is committed. |
| `GET /api/v1/sessions` | Return session history | Excludes revoked or deleted content and uses stable pagination. |
| `DELETE /api/v1/sessions/{id}` | Begin the approved cascade-and-rebuild privacy workflow | Revokes access immediately and returns an auditable asynchronous job status. |
| `GET /api/v1/memories` | Return inspectable bounded conversation memories | Does not expose internal prompts or unrelated learning evidence. |
| `DELETE /api/v1/memories/{id}` | Remove one memory | Immediate and idempotent. It does not mutate learning evidence. |
| `POST /api/v1/exports` | Begin an account data export | Durable job with auditable status and a private expiring download URL. |
| `POST /api/v1/account-deletion` | Begin account erasure | Revokes access, blocks new sessions, and runs a durable deletion workflow. |
| `POST /webhooks/stripe` | Receive subscription, invoice, and checkout lifecycle events | Verifies the raw-body signature, records the event ID, then applies a monotonic internal projection. |

M0 should turn this scope into complete schemas, status codes, error codes, authorization cases, pagination rules, idempotency behavior, and OpenAPI examples. Routes are not ready for implementation until those contract details and the session state machine agree.

## Authentication and browser security

Google authenticates identity through OpenID Connect. Mori authorizes product access through its own user, session, subscription, grant, and usage records.

Required controls:

- Authlib handles OIDC with authorization code flow, PKCE, state, and nonce validation.
- Request only basic OpenID profile and email scopes. Sign-in alone does not require offline access.
- Link an external identity to one application user idempotently.
- Store only an opaque, revocable application session identifier in the browser cookie.
- Use an `HttpOnly`, `Secure`, `SameSite=Lax`, host-only cookie for `api.mori`.
- Allow credentialed CORS only from the exact `mori` origin and explicitly configured local or staging origins.
- Validate CSRF tokens and trusted `Origin` or `Referer` policy on unsafe cookie-authenticated requests.
- Rotate or revoke server-side sessions on logout, account security action, and account deletion.
- Keep auth callback destinations on an allowlist. Never reflect an arbitrary return URL.
- Avoid placing session identifiers, OAuth codes, tokens, or sensitive application state in logs.

The web origin and API origin are separate hosts under the same site. Cookie, CORS, and CSRF behavior must be tested in the deployed topology, not only on localhost.

## Realtime provider boundary

The API accepts the browser SDP offer and exchanges it with OpenAI using the server credential. The response gives the browser only the SDP answer needed for the call.

The integration must:

- Persist the provider call ID and absolute server deadline before treating the session as active.
- Attach a server-side sideband connection through the dedicated supervisor.
- Keep model name, voice, prompts, and provider behavior runtime-configured and version-labeled.
- Persist event IDs and ordering metadata needed for idempotent normalization.
- Enforce the 20-minute limit through server state and provider hangup, independent of the browser.
- Treat provider events as untrusted input and validate their shape before domain handling.
- Use a privacy-preserving stable safety identifier derived with a separately managed secret.

The direct media path minimizes latency, but it does not transfer session policy to the browser or provider.

## Consented audio boundary

Retained learner audio is separate from the WebRTC conversation path. Conversation, transcript-based recap, and non-pronunciation learning continue when a learner declines recording or capture fails.

### Consent and capture

1. The API records session ID, purpose, policy version, grant or revocation, and timestamp.
2. Only after a grant does the API issue scoped multipart-upload URLs.
3. The browser duplicates only the learner microphone track through a versioned capture adapter. AI output is not recorded.
4. Revocation aborts an incomplete upload and queues deletion of completed parts or objects.

### Private storage

- Store audio under a private, session-scoped S3 prefix.
- Block all public access and require SSE-KMS.
- Limit presigned URL expiry, part count, content type, total size, and allowed browser origin.
- Persist checksum, format, duration, state, consent reference, and expiry in PostgreSQL.
- Never treat possession of an object key as authorization.

### Analysis and deletion

- The worker reads an asset only when consent remains current, the asset is complete, and retention has not expired.
- Missing, invalid, revoked, or expired audio produces insufficient pronunciation evidence.
- Audio-derived evidence cannot affect progression until the evaluator passes the approved quality threshold.
- Session or account deletion denies access immediately, queues object deletion, records confirmation, and relies on an S3 lifecycle rule as a backstop.

The exact audio retention period remains unresolved and blocks this path from implementation. Transcript retention is 90 days for the beta.

## Billing boundary

Stripe owns payment processing and subscription lifecycle. Mori owns plans, capabilities, grants, reservations, usage windows, and authorization.

- Map Stripe price IDs to immutable internal plan versions.
- Never branch authorization on a display name or Stripe product name.
- Verify webhook signatures against the untouched request body before parsing.
- Store each provider event ID before applying it and make replays no-ops.
- Apply only valid monotonic subscription transitions or explicitly reconcile out-of-order events.
- Resolve the effective internal entitlement at every protected server entry point.

Tax, refund, failed-payment, cancellation, and grace-period policy must be approved before live billing launches.

## Secrets and configuration

Secrets must live in ignored local environment files for development and a managed secret store in deployed environments. Never commit them or include them in client bundles.

| Integration | Required secret or configuration |
| --- | --- |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_REALTIME_MODEL`, `OPENAI_EXTRACTOR_MODEL`, `OPENAI_SAFETY_ID_SECRET` |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SIGNING_KEY`, `OAUTH_STATE_KEY` |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_BASIC_PRICE_ID` |
| Application | Database URL, exact web origin, cookie settings, KMS key, bucket names, and retention policy versions |

Configuration validation must fail startup for missing or incompatible required values. Development, staging, and production use separate provider projects or accounts and separate secrets.

## Observability and sensitive data

Use structured logs and OpenTelemetry with shared correlation identifiers for HTTP requests, sessions, provider calls, analysis runs, and privacy jobs.

General telemetry must never contain:

- Transcript text or retained audio.
- Memories or conversation hooks.
- OAuth tokens, session cookies, API keys, or presigned URLs.
- Raw model prompts or complete provider payloads.
- Sensitive free-form feedback.

Record bounded identifiers, lifecycle states, durations, counts, provider error categories, and version labels. Security and audit records must have explicit access controls and retention rather than relying on general application logs.

## Security verification gates

- Browser tests cover cookie attributes, exact-origin CORS, CSRF rejection, and callback allowlisting in a production-like domain topology.
- Contract tests cover authentication, ownership, invalid state, idempotent replay, and sanitized errors for every mutation.
- Webhook tests cover invalid signatures, duplicate events, and out-of-order delivery.
- Upload tests prove consent-first issuance, scope limits, revoked access, checksum validation, and lifecycle deletion.
- Threat modeling covers account takeover, entitlement races, provider credential exposure, prompt injection into extraction, transcript access, presigned URL misuse, and incomplete deletion.

# Architecture decisions

**Decision date:** September 2, 2026

**Status:** Accepted baseline unless an entry says open

This file is the compact decision record for the Mori backend. Update an entry in place only to clarify it. A material reversal should mark the original decision superseded, identify the replacement, and describe migration consequences.

## Decision index

| ID | Decision | Status |
| --- | --- | --- |
| ADR-001 | Use a Python modular monolith with three process types | Accepted |
| ADR-002 | Use PostgreSQL as the source of truth and durable queue substrate | Accepted |
| ADR-003 | Use REST, Pydantic, OpenAPI, and a generated web client | Accepted |
| ADR-004 | Use Google OIDC with opaque database-backed application sessions | Accepted |
| ADR-005 | Use direct WebRTC media with server SDP exchange and sideband supervision | Accepted |
| ADR-006 | Retain learner audio only through explicit per-session opt-in | Accepted with open policy values |
| ADR-007 | Cascade session deletion and rebuild derived learning state | Accepted for M4 |
| ADR-008 | Reset beta weekly usage in `America/New_York` | Accepted |
| ADR-009 | Keep manual snapshot review retrospective | Accepted |
| ADR-010 | Use AWS managed containers as the production baseline | Accepted |
| ADR-011 | Model operational facts as typed relational records | Accepted |

## ADR-001: Python modular monolith with three process types

**Decision:** Build one Python backend package and image with `mori-api`, `mori-realtime-supervisor`, and `mori-analysis-worker` entry points.

**Why:** Entitlements, session state, analysis, and learner progression require strong transactions and shared rules. HTTP traffic, active sideband calls, and queued work have different scaling and failure behavior, so they run as separate processes without becoming separately versioned services.

**Consequences:**

- One package, image, release version, migration stream, and database.
- Business modules communicate through command and query interfaces.
- Processes communicate through committed PostgreSQL state, notifications, and jobs rather than private HTTP.
- A module or runtime can be extracted later only when its data ownership and transaction boundary are proven.

**Rejected baseline:** Independently deployed microservices would introduce distributed transactions and contract overhead before the domain boundaries have operational evidence.

## ADR-002: PostgreSQL source of truth and durable queue substrate

**Decision:** Store application records, ledgers, transcripts, evidence, snapshots, leases, and Procrastinate jobs in PostgreSQL.

**Why:** PostgreSQL provides the constraints, row locks, versioning, provenance relationships, and transactional job insertion required by the learning loop. Inserting the analysis job in the same transaction as session finalization avoids a broker dual write.

**Consequences:**

- Procrastinate is hidden behind a queue port so the library can be replaced without leaking into domain behavior.
- Job payloads contain stable identifiers and version pins only.
- `NOTIFY` improves wake-up latency, while indexed scans remain the durable recovery mechanism.
- Real PostgreSQL concurrency, migration, and queue tests are mandatory.

## ADR-003: REST, Pydantic, OpenAPI, and generated clients

**Decision:** Use FastAPI with Pydantic v2. Generate OpenAPI from server schemas, then generate and commit a TypeScript client and Zod validators for the React application.

**Why:** The existing web application already has `WebAppGateway` and realtime ports. A versioned REST surface keeps mutation behavior explicit while generated types prevent the mock and production gateways from drifting.

**Consequences:**

- Every route declares request and response schemas.
- HTTP view models remain distinct from persistence models.
- CI exports the contract and fails on uncommitted drift.
- The SDP route uses `application/sdp` alongside the JSON API.

## ADR-004: Google OIDC and opaque application sessions

**Decision:** Use Authlib for Google OpenID Connect and store opaque, revocable application sessions in PostgreSQL. Send only the opaque ID in a host-only secure cookie for `api.mori`.

**Why:** Google proves identity while Mori retains control of session revocation, account status, entitlements, and authorization.

**Consequences:**

- Use PKCE, state, nonce, minimal scopes, exact credentialed CORS, and CSRF protection.
- Provision the application user, language profile, and intro grant idempotently.
- Do not use Google tokens as application authorization tokens or expose them to the web application.

## ADR-005: Direct WebRTC with server supervision

**Decision:** Exchange the browser SDP offer through the API, then send live media directly between the browser and OpenAI Realtime. A dedicated supervisor attaches through the provider sideband connection.

**Why:** Direct media keeps latency low. Server-side call identity, event observation, leases, and hangup preserve the trusted 20-minute cap and durable transcript path.

**Consequences:**

- Persist provider call ID, absolute deadline, connected segments, event watermark, and renewable supervisor lease.
- The API process does not own the timer after its response.
- Provider hangup and finalization must be safe to repeat.
- Model and voice identifiers are runtime configuration selected after evaluation.

## ADR-006: Explicit per-session audio opt-in

**Decision:** Conversation does not require recording. Retain only the learner microphone track after an explicit, versioned, per-session consent grant. Upload directly to private S3 with SSE-KMS and analyze asynchronously.

**Why:** Transcript text and ASR confidence cannot support tone- or phoneme-level learning claims. Explicit opt-in permits higher-quality pronunciation analysis while isolating its privacy and storage lifecycle.

**Consequences:**

- No consent or unusable audio means insufficient pronunciation evidence.
- AI output is never retained through this path.
- Consent precedes upload URL creation and can be revoked.
- Audio-derived evidence cannot affect progression until its evaluator meets an approved quality threshold.
- Audio has a retention period separate from the 90-day transcript default.

**Alternatives considered:**

- Transcript-only pronunciation evidence was rejected because it cannot justify fine-grained pronunciation claims.
- A transient live assessment adapter remains a future option, but would still require a validated evaluator and bounded score provenance.

**Open values:** Audio retention duration and the pronunciation evaluator quality threshold.

## ADR-007: Cascade session deletion and rebuild

**Decision:** Deleting a session removes its transcript, recap, memories, conversation hooks, retained audio, and session-derived learning evidence. Mori then recomputes affected learner state from the remaining evidence and appends a corrective snapshot.

**Why:** Learners should not retain invisible progress whose original evidence they intentionally deleted. Rebuild keeps provenance honest and deletion behavior understandable.

**Consequences:**

- Revoke access immediately and complete database and object deletion through a durable workflow.
- Historical evidence from other sessions remains immutable.
- The corrective decision and snapshot are appended rather than editing earlier history.
- This workflow ships in M4, not the first live slice.
- Transcript retention defaults to 90 days for beta unless legal or privacy review changes it.

**Rejected alternatives:** Deleting only the visible transcript would preserve claims the learner can no longer inspect. Account-lifetime retention would create unnecessary privacy exposure.

## ADR-008: Weekly reset in `America/New_York`

**Decision:** Beta weekly entitlement windows open Monday at 00:00 in the IANA zone `America/New_York`.

**Why:** The product requirement describes a US Eastern weekly boundary. An IANA timezone follows daylight saving changes correctly, unlike a fixed UTC-05:00 offset.

**Consequences:**

- Persist the exact UTC start and end of every created window.
- Test spring and fall daylight saving transitions.
- A future per-learner timezone change affects the next unopened window and does not rewrite an active or historical window.

## ADR-009: Retrospective manual review

**Decision:** Risk rules sample completed learner snapshots for retrospective review. Review does not block the 60-second recap target or the next otherwise-valid session.

**Why:** Human calibration is valuable, but synchronous review would create an unbounded availability and operations dependency.

**Consequences:**

- Reviewer corrections append an auditable decision and derived snapshot.
- Historical evidence and prior decisions remain unchanged.
- Review queues, outcomes, reviewer identity, and correction reasons are first-class records.

## ADR-010: AWS managed containers

**Decision:** Use AWS ECS Fargate, RDS PostgreSQL, S3, KMS, Secrets Manager, Route 53, ACM, WAF, ALB, and CloudFront as the production baseline, provisioned through Terraform.

**Why:** Long-lived sideband sockets and workers fit container processes. RDS and S3 provide the required durable database, private object storage, backup, and lifecycle controls.

**Consequences:**

- Keep the application portable through standard containers, PostgreSQL, migrations, and an object-storage port.
- Isolate staging and production, preferably in separate AWS accounts.
- Keep databases and buckets private, encrypt backups and objects, rotate secrets, and prove restore before beta.
- The primary AWS region remains an owner decision based on cohort location and legal requirements.

**Alternatives considered:** A managed container PaaS remains viable for a local or early prototype, but it is not the production baseline. Deferring the provider would postpone required security and recovery design.

## ADR-011: Typed relational operational facts

**Decision:** Store consent versions, preferences, provider events, connection segments, leases, webhook receipt, curriculum publication, audio assets, retention policy, safety reports, reviews, and audit events as typed records with lifecycle state and constraints.

**Why:** These records affect correctness, privacy, recovery, and explanation. Hiding them in generic JSON or logs makes invariants unenforceable and repair unsafe.

**Consequences:**

- Use selective JSONB only for bounded, versioned metadata without relational integrity needs.
- Include these concepts in the initial ERD and migration plan.
- Define explicit retention and access rules for audit and safety records.

## Technology choices

| Concern | Choice | Constraint |
| --- | --- | --- |
| Repository | Polyglot monorepo with uv for Python and npm for web | Pin Python 3.13 and Node 22. Keep native lockfiles. |
| Data access | SQLAlchemy 2.0, psycopg 3, and Alembic | Prefer explicit Core statements for ledgers and bulk evidence writes. Never auto-migrate on application boot. |
| Background work | Procrastinate | IDs-only idempotent tasks behind a queue port. |
| Extraction | OpenAI Responses with strict structured output | Persist model, prompt, schema, analyzer, and policy versions. The model proposes only. |
| Billing | Stripe Billing and signed webhooks | Internal versioned plans authorize access. Store and deduplicate provider events. |
| Observability | structlog and OpenTelemetry | Never export transcripts, audio, memories, credentials, or raw prompts to general telemetry. |
| Testing | pytest, Testcontainers, Hypothesis, Vitest, and Playwright | Concurrency, replay, contract, migration, and browser security tests are release gates. |

## Open owner decisions

| Decision | Blocks | Required outcome |
| --- | --- | --- |
| Audio retention duration | Audio schema, consent copy, lifecycle rule, and audio upload implementation | Approve a duration shorter than transcript retention and its legal basis. |
| Pronunciation evaluator threshold | Audio-derived evidence and promotion | Approve the evaluation corpus, metric, minimum threshold, and rollback rule. |
| Realtime and extraction model aliases | Production provider configuration | Select only after latency, quality, safety, and cost evaluation. |
| Stripe tax, refund, failed-payment, cancellation, and grace policy | Live billing | Approve lifecycle behavior that maps provider events to internal access. |
| AWS primary data region | Production infrastructure | Select from cohort location and legal or privacy requirements. |
| Telemetry backend, alert destinations, and incident owner | Controlled beta | Name the backend and operational ownership, then verify alerts. |
| First published curriculum and promotion rules | Planning and durable learning loop | Approve versioned source data and deterministic gate rules. |

Open values do not weaken the surrounding invariant. A feature whose safe behavior depends on an open value remains disabled until that value and its tests are approved.

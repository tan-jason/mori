# Modules and data

Mori uses business capabilities as module boundaries inside one Python application. Each module exposes application commands and queries, owns its persistence model, and protects its invariants. Route functions, supervisor loops, and task handlers call those interfaces instead of constructing cross-module SQL.

## Dependency direction

```text
transport and runtime entry points
              |
              v
      application use cases
              |
              v
        domain services
              |
              v
     repository/provider ports
              ^
              |
     PostgreSQL/provider adapters
```

Rules:

- The domain layer does not import FastAPI, SQLAlchemy models, provider SDKs, or runtime entry points.
- Application use cases coordinate domain services and repository ports and define transaction boundaries.
- Adapters implement ports for PostgreSQL, OpenAI, Google, Stripe, and object storage.
- HTTP schemas and persistence entities do not become domain models by default.
- A module may query another module through its public query interface and mutate it only through its public command interface.
- Read-model composition may join stable projections for reads but cannot bypass commands for writes.
- Cyclic imports between business modules fail an architecture test.

Session creation may coordinate access and curriculum planning in one unit of work. Realtime control may invoke session commands. Analysis consumes an immutable session bundle and curriculum version, then invokes learning commands. Billing affects access only through the access application interface.

## Logical modules

### Identity and learner profile

Owns Google identity linking, opaque application sessions, idempotent user provisioning, language profiles, preferences, consent versions, and account status.

- Commands: `complete_sign_in`, `update_preferences`, `record_consent`
- Queries: `current_learner`
- Records: `users`, `auth_sessions`, `language_profiles`, `learner_preferences`, `user_consents`

### Access and billing

Owns the internal plan catalog, intro and paid grants, usage windows, reservations, consumption ledger, Stripe subscription projection, and webhook deduplication. Stripe never authorizes product access directly.

- Commands: `reserve_session`, `consume_reservation`, `release_reservation`, `apply_stripe_event`
- Queries: `access_decision`, `current_usage`
- Records: `plan_versions`, `entitlement_rules`, `subscriptions`, `grants`, `usage_reservations`, `usage_events`, `webhook_events`

The beta weekly window opens Monday at 00:00 in `America/New_York`. Store each window's exact UTC start and end. Do not implement this as a fixed UTC-05:00 offset because daylight saving transitions must follow the IANA zone.

### Curriculum and planning

Owns the versioned learning graph, prerequisites, evidence rules, deterministic objective selection, placement, and immutable session plans.

- Commands: `publish_curriculum`, `build_session_plan`
- Queries: `curriculum_version`, `eligible_objectives`
- Records: `curriculum_versions`, `curriculum_items`, `curriculum_edges`, `evidence_rules`, `session_plans`, `plan_objectives`

A plan pins its curriculum version, learner snapshot, selection-rule version, and no more than three objectives. Optional model assistance may shape a theme or ordering, but cannot waive prerequisites, unlock content, or change the learner's level.

### Session orchestration

Owns the conversation state machine, ownership checks, idempotent creation, connection segments, usable-session policy, reconnect behavior, end reason, transcript watermark, and analysis handoff.

- Commands: `create_session`, `begin_connect`, `activate_call`, `request_end`, `finalize_session`
- Queries: `session_status`, `transcript_bundle`
- Records: `sessions`, `session_connections`, `session_turns`

Session orchestration is the only module allowed to transition session state. Realtime control supplies normalized facts through session commands instead of updating the session row directly.

### Realtime control

Owns OpenAI SDP and sideband adapters, supervisor leases, provider-event normalization, ordered turn ingestion, deadlines, interruption handling, hangup, and the consent-gated browser capture contract.

- Commands: `exchange_sdp`, `claim_supervision`, `ingest_event`, `enforce_deadline`, `create_audio_upload`
- Queries: `recoverable_calls`
- Records: `realtime_events`, `supervisor_leases`, `audio_consents`, `session_audio_assets`

Provider payloads are normalized at the adapter boundary. Preserve provider event identifiers and sequence metadata required for deduplication and debugging, while keeping provider-specific payloads out of domain decisions.

### Learning and analysis

Owns versioned extraction schemas, provenance validation, evidence append, pure progression rules, current item state, level assessment, recap, snapshots, bounded memories, and conversation hooks.

- Commands: `analyze_session`, `validate_candidates`, `apply_evidence`
- Queries: `recap`, `learner_snapshot`, `memories`
- Records: `analysis_runs`, `learning_evidence`, `learner_item_states`, `level_assessments`, `learner_state_snapshots`, `recaps`, `memories`, `conversation_hooks`

Model output cannot write these records. An application service validates candidates against exact turn IDs and pinned versions, then pure rules determine the committed changes.

### Privacy, safety, and operations

Owns versioned retention policies, transcript and audio expiry, session deletion, account erasure, exports, feedback, safety incidents, retrospective review, audit records, and repair commands.

- Commands: `expire_assets`, `delete_session`, `request_export`, `erase_account`, `report_feedback`, `correct_snapshot`
- Queries: `privacy_job_status`, `review_queue`
- Records: `retention_policies`, `privacy_jobs`, `export_manifests`, `safety_reports`, `snapshot_reviews`, `audit_events`

Privacy workflows use explicit lifecycle states. They revoke access synchronously where possible, enqueue durable work in the same commit, and record external object deletion confirmation.

### Read models and contracts

This thin composition layer builds responses for the dashboard, history, recap, and other frontend views from module query interfaces.

- Queries: `dashboard_snapshot`, `session_history`, `recap_view`
- Source-of-truth records: none

Pydantic HTTP models generate OpenAPI. The generated TypeScript client and runtime validators implement the production `WebAppGateway`. Read models are allowed to denormalize or join projections for query efficiency, but their shape does not define write ownership.

## Data domains

| Domain | Purpose | Primary records |
| --- | --- | --- |
| Identity | Account, authentication, language profile, preferences, and consent | `users`, `auth_sessions`, `language_profiles`, `learner_preferences`, `user_consents` |
| Access | Versioned plans, capabilities, subscriptions, grants, reservations, usage, and provider deduplication | `plan_versions`, `entitlement_rules`, `subscriptions`, `grants`, `usage_reservations`, `usage_events`, `webhook_events` |
| Live | Session state, immutable plan, connection history, ordered turns, provider facts, leases, and consented audio metadata | `sessions`, `session_connections`, `session_plans`, `plan_objectives`, `session_turns`, `realtime_events`, `supervisor_leases`, `audio_consents`, `session_audio_assets` |
| Curriculum | Published competency graph, dependencies, and evidence policy | `curriculum_versions`, `curriculum_items`, `curriculum_edges`, `evidence_rules` |
| Learning | Append-only evidence, derived item state, assessments, and immutable snapshots | `learning_evidence`, `learner_item_states`, `level_assessments`, `learner_state_snapshots` |
| Analysis and privacy | Versioned runs, learner-facing output, bounded memory, retention, deletion, review, safety, and audit | `analysis_runs`, `recaps`, `memories`, `conversation_hooks`, `retention_policies`, `privacy_jobs`, `export_manifests`, `snapshot_reviews`, `safety_reports`, `audit_events` |

This list establishes ownership and required concepts, not a final physical schema. M0 must produce the reviewed ERD, constraints, indexes, and migration order before implementation begins.

## Relational modeling rules

- Use UUID or another non-sequential public identifier for externally addressable records.
- Use `timestamptz` for instants and store explicit IANA timezone names when local-time policy matters.
- Enforce state values, positive durations, byte limits, and other bounded values with database constraints where practical.
- Use foreign keys for ownership and provenance. Avoid polymorphic string references for core records.
- Represent versioned product policy with immutable versions and explicit publication state.
- Use JSONB only for bounded provider metadata, versioned structured payloads, or fields without relational query and integrity requirements.
- Keep evidence, usage events, audit events, assessment decisions, and snapshots append-only where promised.
- Give every provider webhook, realtime event, job intent, and externally retried command a unique deduplication key.
- Index recovery queries such as expired supervisor leases, active sessions by deadline, unexpired reservations, due jobs, and retention expiry.
- Treat soft deletion as access revocation, not proof of erasure. Privacy jobs must track physical data and object deletion to completion.

## Core invariants

### Entitlement ledger

- Intro grants are unique per account and never reset.
- A reservation belongs to exactly one session attempt.
- The sum of active reservations and consumed usage cannot exceed the effective grant within a usage window.
- A session consumes its reservation after its first usable learner turn.
- Setup failure with no usable learner turn releases the reservation.
- Reservation, consumption, and release are idempotent ledger events, not mutable counters without history.

### Session and transcript

- One session has at most one active provider call.
- Connected duration is the sum of persisted connection segments and cannot exceed the server cap by policy.
- Turn ordering is stable and provider-event replay cannot create duplicate turns.
- Analysis input is bounded by a fixed final turn watermark.
- Reconnect adds a connection segment and never resets consumed connected time.

### Learning

- Every evidence record cites valid turns from its source session.
- Evidence records pin extraction, schema, prompt, model, curriculum, and rule versions needed for explanation or replay.
- Current item state and level are derived from accepted evidence through deterministic rules.
- A completed analysis commit contains its evidence, derived state, recap, snapshot, and run status together.
- Corrections append new decisions and snapshots without rewriting historical evidence.

### Consent and retained files

- An audio upload cannot be created before session-specific consent is persisted.
- Only the learner microphone track is eligible for retention. AI output is not recorded.
- A completed asset has bounded size, format, duration, checksum, storage key, consent reference, and expiry.
- The worker checks current consent, completion, and expiry each time before reading audio.
- Revocation immediately denies new reads and schedules multipart abort or object deletion.

## Session deletion and rebuild

The approved beta behavior is cascade and rebuild:

1. Mark the session inaccessible to the learner and block new processing from using it.
2. Revoke audio access and enqueue durable database and object deletion work.
3. Delete the session transcript, recap, memories, conversation hooks, associated audio, and learning evidence derived from the session.
4. Recompute affected item state and level decisions from the remaining append-only evidence.
5. Append a corrective learner snapshot and audit event.
6. Record completion only after required object deletions are confirmed.

Transcript retention defaults to 90 days for the beta. Audio requires a separate, shorter retention value before its implementation. S3 lifecycle expiration is a defense-in-depth backstop and does not replace application deletion tracking.

## Architecture tests

At minimum, automated architecture tests should enforce:

- Domain modules do not import transport, runtime, SQLAlchemy model, or provider SDK packages.
- Route modules do not import another module's persistence models.
- Business-module imports are acyclic.
- Provider adapters implement declared ports and are not called from pure domain code.
- Generated OpenAPI is reproducible and the committed TypeScript client is current.

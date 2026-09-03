# Architecture references

This file preserves the evidence behind the September 2, 2026 backend architecture baseline. Product documents justify Mori-specific behavior. Provider and framework documentation justifies integration capabilities, not product policy.

## Repository sources

- [Product requirements](../PRD.md) defines session, entitlement, evidence, privacy, safety, and acceptance behavior.
- [High-level system design](../diagrams/high-level-system-design.md) defines the live and post-session trust boundaries.
- [Web application integration notes](../../apps/web/README.md) define the current frontend handoff, trusted timer, and gateway requirements.
- [`WebAppGateway`](../../apps/web/src/api/web-app-gateway.ts) is the existing application-data port.
- [`RealtimeSessionFactory`](../../apps/web/src/realtime/realtime-session.ts) is the existing realtime transport port.

## Provider and framework sources

- [OpenAI Realtime with WebRTC](https://developers.openai.com/api/docs/guides/realtime-webrtc) describes server SDP exchange and browser connection patterns.
- [OpenAI Realtime server controls](https://developers.openai.com/api/docs/guides/realtime-server-controls) describes provider call IDs and sideband server control.
- [OpenAI Realtime hangup](https://developers.openai.com/api/reference/python/resources/realtime/subresources/calls/methods/hangup) describes server-initiated call termination.
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) describes schema-constrained model output and Pydantic integration.
- [FastAPI features](https://fastapi.tiangolo.com/features/) describes Pydantic request handling, OpenAPI generation, and client generation support.
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/) describes the selected Python data layer and PostgreSQL support.
- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/) describes ordered SQLAlchemy migration management.
- [Procrastinate external connection](https://procrastinate.readthedocs.io/en/stable/howto/production/external_connection.html) describes enqueuing work with an application-managed PostgreSQL connection and transaction.
- [Authlib Starlette client](https://docs.authlib.org/en/v1.6.1/client/starlette.html) describes the selected async OpenID Connect integration used by FastAPI's underlying Starlette layer.
- [Stripe subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks) describes subscription and payment lifecycle delivery.
- [OpenTelemetry for Python](https://opentelemetry.io/docs/languages/python/) describes the vendor-neutral instrumentation baseline.

## Verification policy

Provider behavior and library support can change. Before implementing a milestone that depends on an external capability:

1. Recheck the relevant official documentation against the pinned SDK or service version.
2. Capture the supported request, response, event, retry, and lifecycle behavior in an adapter contract test.
3. Record a new architecture decision if current provider behavior requires a boundary or invariant to change.

Do not treat a documentation link as a substitute for an integration test against the configured development project.

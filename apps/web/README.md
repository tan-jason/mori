# Mori webapp

Responsive React foundation for Mori's learner experience. It includes the home,
pre-session, recap, and remembered-information surfaces described in the PRD.

English is the fixed base language. The mock profile defaults to Mandarin, and the
webapp supports Spanish, French, Portuguese, Japanese, Korean, and Vietnamese. The
active language comes from the learner's server-owned language profile. Its profile
ID is included in query keys and gateway calls so course data stays isolated by
target language. Changing languages belongs in a separate account workflow rather
than an inline page control.

Auth, backend transport, data mutations, microphone access, and the realtime voice
agent are intentionally outside this scaffold.

## Run locally

```bash
cd apps/web
npm install
npm run dev
```

Quality checks:

```bash
npm run lint
npm test
npm run build
```

The current toolchain requires Node.js 22.13 or newer.

## Source boundaries

```text
src/
  api/          Learner-facing backend port and mock adapter
  app/          Providers and route composition
  components/   Shared application shell and states
  domain/       Webapp view models
  features/     Route-owned UI and query hooks
  realtime/     Typed future WebRTC session port
  styles/       Responsive design system and global styles
```

Features consume `WebAppGateway`, not `fetch` or backend persistence entities. When
the application API is ready, add a production gateway implementation and inject it
through `AppProviders`. Keep response validation in that adapter so feature code only
receives valid view models.

The realtime implementation belongs behind `RealtimeSessionFactory`. It should use a
short-lived credential or SDP exchange from the application backend and must never
ship a standard provider API key to the browser.

## System design handoff notes

- The browser-to-backend and browser-to-realtime-provider boundaries match the
  high-level diagram.
- The backend must remain authoritative for entitlements, connected time, the
  20-minute cap, session status, and transcript persistence. Client displays are not
  enforcement mechanisms.
- Transcript persistence and post-session job dispatch need an atomic handoff, such
  as a transactional outbox. Independent persist and enqueue writes can strand a
  completed session without analysis.
- The eventual diagram should make the short-lived realtime session bootstrap flow
  explicit. The direct WebRTC edge must not imply that the browser holds provider
  credentials.
- Observability is currently positioned in the diagram but not connected to the live
  or post-session paths. Instrument both flows when their implementation begins.

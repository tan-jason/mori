# Mori webapp

Responsive React foundation for Mori's learner experience. It includes the home,
pre-session, recap, and remembered-information surfaces described in the PRD.

English is the fixed base language. The mock profile defaults to Mandarin, and the
webapp supports Spanish, French, Portuguese, Japanese, Korean, and Vietnamese. The
active language comes from the learner's server-owned language profile. Its profile
ID is included in query keys and gateway calls so course data stays isolated by
target language. Changing languages belongs in a separate account workflow rather
than an inline page control.

Google sign-in, application session restoration, learner account details, preference
updates, and sign-out use the backend API. Dashboard, recap, and memory content still
use the deterministic preview adapter until their read endpoints land. Microphone
access and the realtime voice agent remain outside this slice.

## Run locally

```bash
cd apps/web
npm install
npm run dev
```

The webapp reads `VITE_API_ORIGIN` from the root `.env` and defaults to
`http://localhost:8000`. Set `VITE_USE_MOCK_API=true` only when working on the
webapp without the backend. For end-to-end identity testing, start PostgreSQL, apply
the backend migrations, run the API, then run the webapp. See the backend README for
the exact commands and Google OAuth configuration.

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

Features consume `WebAppGateway`, not `fetch` or backend persistence entities. The
production gateway includes credentials on API requests and validates identity
responses before exposing view models to features. The mock gateway remains available
for isolated frontend work and tests.

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

# Mori webapp

Responsive React foundation for Mori's learner experience. It includes the home,
pre-session, recap, and remembered-information surfaces described in the PRD.

New learners choose their base and target languages, starting point, tutor style, and optional
interests during onboarding. All listed target languages use Mori's shared course.
The active language comes from the learner's server-owned language profile. Its profile ID is
included in query keys and gateway calls so course data stays isolated by target language.
Changing languages belongs in a separate account workflow rather than an inline page control.

Google sign-in, application session restoration, learner account details, preference
updates, and sign-out use the backend API. Dashboard, recap, and memory content still
use the deterministic preview adapter until their read endpoints land. The session
page uses browser WebRTC for microphone audio and the backend for SDP exchange,
call acknowledgement, and ending. It checks backend voice availability before
enabling Begin.

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
Set `VITE_MOCK_ONBOARDING=true` together with `VITE_USE_MOCK_API=true` to preview a new
learner's onboarding flow without Google sign-in.

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
  realtime/     Browser WebRTC session and backend transport
  styles/       Responsive design system and global styles
```

Features consume `WebAppGateway`, not `fetch` or backend persistence entities. The
current backend gateway includes credentials on API requests and validates identity
responses before exposing view models to features. The mock gateway remains available
for isolated frontend work and tests.

The identity gateway is transitional for this bounded M1 slice and currently maintains its
runtime schemas by hand. Before the M1 exit gate, the generated OpenAPI client and Zod validators
become the production implementation, and CI must reject contract drift.

The realtime implementation sits behind `RealtimeSessionFactory`. It exchanges SDP
through the application backend and never ships a standard provider API key to the browser.

## System design handoff notes

- The browser-to-backend and browser-to-realtime-provider boundaries match the
  high-level diagram.
- The backend must remain authoritative for entitlements, connected time, the
  10-minute cap, session status, and transcript persistence. Client displays are not
  enforcement mechanisms.
- Transcript persistence and post-session job dispatch need an atomic handoff, such
  as a transactional outbox. Independent persist and enqueue writes can strand a
  completed session without analysis.
- The eventual diagram should make the short-lived realtime session bootstrap flow
  explicit. The direct WebRTC edge must not imply that the browser holds provider
  credentials.
- Observability is currently positioned in the diagram but not connected to the live
  or post-session paths. Instrument both flows when their implementation begins.

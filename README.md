# Mori

Mori is a planned voice-first language learning app built around natural conversation, personalized practice, and evidence-based progression. Its conversation course is shared across the supported target languages.

> Status: Webapp foundation and backend identity foundation are in progress. Realtime and
> learning integrations are not implemented.

## Product vision

Mori is designed to give English-speaking learners regular, realistic speaking practice without losing the structure of a curriculum. Each conversation should feel natural while still targeting a small set of learning objectives.

The tutor will remember useful learning context, adapt to the learner's demonstrated ability, revisit skills over time, and help the learner express ideas with the target language they already know.

## MVP experience

- Learners explicitly select a supported base and target language during onboarding. No language is preselected.
- Learners can choose from the supported target languages and use Mori's shared course with each one.
- Learners receive a provisional Beginner level when they are unsure of their starting ability.
- The learning system has four levels: Beginner, Intermediate, Advanced, and Fluent practice mode.
- Sessions are voice-first, may end at any time, and have a 10-minute maximum.
- Each session focuses on one to three personalized learning objectives.
- The selected target remains the default conversation language.
- Brief, compassionate help in the selected base language is available when a learner is stuck.
- Post-session processing extracts transcript-grounded learning evidence and prepares future practice.
- Progression is computed through versioned product rules rather than model intuition alone.

## Learning philosophy

Mori encourages productive effort without shame:

> Always try your best to speak your target language. If you do not know a word, use the language you already know to describe what you mean. Your tutor will help you build the missing word or phrase without judgment.

Exposure is not treated as mastery. Vocabulary, concepts, and level changes require demonstrated evidence across meaningful opportunities.

## Planned technical direction

| Area | Direction |
| --- | --- |
| Client | Responsive web application |
| Live conversation | Speech-to-speech sessions over WebRTC |
| Tutor | Low-latency realtime conversation with level-adaptive prompting |
| Curriculum | Versioned competency graph with deterministic selection |
| Session analysis | Separate structured extraction after each usable session |
| Progression | Versioned, deterministic validation backed by transcript evidence |
| Personalization | Learning records kept separate from bounded conversation memory |

These are product decisions, not completed implementation. Model, voice, API, and infrastructure choices must be validated when development begins.

## Documentation

- [Product requirements document](docs/PRD.md)
- [Learning system PRD](docs/learning-system-prd.md)
- [High-level system design](docs/diagrams/high-level-system-design.md)
- [Backend architecture](docs/architecture/README.md)
- [Learning system implementation design](docs/architecture/learning-system-implementation.md)
- [Learning system data contracts](docs/architecture/learning-system-data-contracts.md)
- [Backend implementation plan](docs/plans/backend-implementation.md)
- [Webapp foundation](apps/web/README.md)

The original PRD defines the broader MVP scope. The learning system PRD owns the updated language selection, level, tutor, planning, learning, and memory behavior. The implementation design contains the five workflow diagrams and delivery gates; the data contracts define the table relationships and object fields. The backend architecture covers the shared runtime, API, security, and operations foundations.

## Repository status

The responsive webapp scaffold lives in `apps/web`. Its account flow is connected to the backend for Google sign-in, application sessions, learner profiles, preferences, and sign-out. Learning content still uses a preview adapter while those APIs are built. See each application README for local setup and integration notes.

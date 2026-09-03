# Mori

Mori is a planned voice-first language learning app built around natural conversation, personalized practice, and evidence-based progression. Mandarin is the initial MVP course.

> Status: Webapp foundation in progress. Backend and realtime integrations are not implemented.

## Product vision

Mori is designed to give English-speaking learners regular, realistic speaking practice without losing the structure of a curriculum. Each conversation should feel natural while still targeting a small set of learning objectives.

The tutor will remember useful learning context, adapt to the learner's demonstrated ability, revisit skills over time, and help the learner express ideas with the target language they already know.

## MVP experience

- English is the fixed base language. Standard Mandarin is the default MVP target.
- The webapp foundation supports Mandarin, Spanish, French, Portuguese, Japanese, Korean, and Vietnamese as target languages.
- Learners receive a provisional Beginner level when they are unsure of their starting ability.
- Sessions are voice-first, may end at any time, and have a 20-minute maximum.
- Each session focuses on one to three personalized learning objectives.
- The selected target remains the default conversation language.
- Brief, compassionate English clarification is available when a learner is stuck.
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
- [High-level system design](docs/diagrams/high-level-system-design.md)
- [Backend architecture](docs/architecture/README.md)
- [Backend implementation plan](docs/plans/backend-implementation.md)
- [Webapp foundation](apps/web/README.md)

The PRD defines the MVP scope, user experience, tutor behavior, learning state, functional requirements, technical direction, metrics, safety requirements, and acceptance criteria. The system design defines the high-level component boundaries and end-to-end learning flow. The backend architecture turns those boundaries into runtime, module, data, API, security, and delivery decisions.

## Repository status

The responsive webapp scaffold lives in `apps/web`. It currently uses a mock gateway so frontend work can proceed independently from backend API design. See the webapp README for local setup, source boundaries, and integration notes.

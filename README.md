# Mori

Mori is a planned voice-first Mandarin learning app built around natural conversation, personalized practice, and evidence-based progression.

> Status: Product definition. Application implementation has not started yet.

## Product vision

Mori is designed to give English-speaking learners regular, realistic Mandarin speaking practice without losing the structure of a curriculum. Each conversation should feel natural while still targeting a small set of learning objectives.

The tutor will remember useful learning context, adapt to the learner's demonstrated ability, revisit skills over time, and help the learner express ideas with the Mandarin they already know.

## MVP experience

- English is the fixed base language and Standard Mandarin is the fixed learning language.
- Learners receive a provisional Beginner level when they are unsure of their starting ability.
- Sessions are voice-first, may end at any time, and have a 20-minute maximum.
- Each session focuses on one to three personalized learning objectives.
- Mandarin remains the default conversation language.
- Brief, compassionate English clarification is available when a learner is stuck.
- Post-session processing extracts transcript-grounded learning evidence and prepares future practice.
- Progression is computed through versioned product rules rather than model intuition alone.

## Learning philosophy

Mori encourages productive effort without shame:

> Always try your best to speak Mandarin. If you do not know a word, use the Mandarin you already know to describe what you mean. Your tutor will help you build the missing word or phrase without judgment.

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

The PRD defines the MVP scope, user experience, tutor behavior, learning state, functional requirements, technical direction, metrics, safety requirements, and acceptance criteria.

## Repository status

This repository currently contains product documentation only. Application code, local setup instructions, testing commands, and deployment guidance will be added alongside the implementation.

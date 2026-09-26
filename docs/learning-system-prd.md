# Mori learning system PRD

**Status:** Approved product contract for implementation

**Date:** September 26, 2026

**Scope:** Onboarding inputs, level and practice mode, session planning, live tutor behavior, learning evidence, personal memory, recaps, and the next-session feedback loop.

This document is the product contract for Mori's learning system. It supersedes conflicting learning-specific requirements in [the original MVP PRD](PRD.md), particularly its fixed language pair, six-level framework, and Fluent learning behavior. Entitlements, session duration, authentication, and privacy workflows retain their existing approved contracts unless this document explicitly changes them. The companion implementation design will define APIs, persistence, runtime boundaries, and migration steps.

## 1. Product outcome

Mori helps a learner speak a chosen target language through an engaging voice conversation. For learners in learning mode, each session deliberately practices a small set of eligible skills and uses validated evidence to improve the next plan. A Fluent learner can choose conversation practice without learning advice or mastery tracking.

The tutor carries the conversation: it asks relevant questions about everyday life, responds to answers, asks follow-ups, and pivots when a topic runs out. It pauses that momentum when the learner asks for help or struggles to express an idea, then helps them retry. Objectives and personal context shape the conversation without turning it into a script.

## 2. Scope and boundaries

### In scope

- Explicit base and target language selection during onboarding.
- A provisional starting level and editable tutor preferences.
- Optional, editable interests and optional topic or words requested for an individual session.
- A versioned pre-session plan and a level-aware Realtime tutor prompt.
- Proactive conversation, bounded support-language scaffolding, and gentle pronunciation help.
- Post-session evidence, deterministic learning progress, level assessment, recap, and safe personal memory for learning mode.
- A separate Fluent practice mode with a brief conversation summary and inspectable permitted memories.
- Recovery when analysis is delayed, a memory is deleted, or a session is interrupted.

### Outside this PRD

- Payment, entitlement quantities, authentication, and the 20-minute session cap.
- A specific provider model, voice, cloud region, or price.
- Full curriculum content and numerical assessment thresholds, which must be published and evaluated before release.
- Support for every language shown in the web scaffold. Only language pairs with a published course and voice policy can be selected for a live session.

## 3. Learner profile and onboarding

1. The learner explicitly selects a base language for help and a target language for practice. Neither field has a preselected value. The app shows which language pairs are currently supported.
2. The learner selects an approximate starting level: Beginner, Intermediate, Advanced, or Fluent. They may choose "I'm not sure"; this creates a provisional Beginner placement for learning mode, not an assessed level.
3. The learner selects correction frequency and tutor pace. Existing defaults for these preferences may be offered, but no language can be inferred from them.
4. The learner may enter conversation interests. Interests are optional, editable, and are not treated as evidence of skill or as permission to save sensitive facts.
5. The learner can review the chosen languages, level or mode, and preferences before starting voice practice.

An account may exist without a language profile while onboarding is incomplete. The app must not create a plan or start a conversation until both languages are explicitly selected and the pair is supported. It directs the learner back to the missing onboarding step. A provisional level is not a verified assessment.

The language profile owns language-specific preferences, learning state, memories, and session history. Changing the target language starts or activates a separate profile; it does not reinterpret evidence or memories from another language.

The tutor uses a reusable base conversation policy plus a published policy for the selected language pair. The first course may tailor English base-language support and Mandarin target-language examples, voice, and pronunciation help. The pair is still chosen explicitly by the learner; no language is an application default.

## 4. Four-level framework

These are Mori product levels, not formal certifications.

| Level | Learner ability | Tutor behavior |
| --- | --- | --- |
| Beginner | Knows some words or phrases but cannot sustain a conversation. | Short predictable language, one question at a time, familiar words, supportive retries. |
| Intermediate | Can hold a basic conversation about familiar everyday topics. | Clear connected sentences, follow-up questions, and targeted help when blocked. |
| Advanced | Can handle more complex or abstract conversation. | Mostly natural pace and register, nuanced follow-ups, and selective feedback. |
| Fluent | Primarily wants natural conversation practice. | Natural conversation without unsolicited teaching, learning advice, or mastery tracking. |

There is no separate zero-knowledge tier. Beginner is the lowest product level.

For Beginner through Advanced, self-selection is provisional until a usable diagnostic conversation provides enough evidence. Later promotion or demotion follows published, versioned rules and evidence from valid learner turns. A short, low-quality, or failed session cannot change an assessed level. Changes are explained in plain language.

Fluent selection is a **practice-mode choice**, not a claim that Mori has verified fluency. It takes effect immediately so a learner who wants only practice does not receive an unwanted diagnostic or learning advice. The learner can switch into assessed learning mode later, which starts with a diagnostic. Mori does not silently move someone into or out of Fluent practice mode.

## 5. Before a session

The learner can see a suggested focus and optionally enter a topic or words they want to use. Leaving these fields blank is valid. The app explains that Mori will help them continue in the target language when they get stuck.

For learning mode, Mori creates a plan before connecting audio from:

- The selected language profile, provisional or assessed level, and level confidence.
- The last committed learning snapshot, if one exists.
- Published curriculum gates, due review items, and recent supported repair needs.
- Correction and pace preferences.
- Optional interests, a session topic, and requested words.
- Current, safe conversation hooks and memories, with freshness and expiry.
- Time since the last completed session and the session time budget.

The first session has no learning snapshot. It uses provisional placement and a versioned starter curriculum. If the previous session's analysis is pending or failed, the next plan uses the last committed snapshot. Personal memories are separate from learning evidence and are never treated as proof of ability.

A learning-mode plan contains one to three eligible objectives, normally a review or repair goal, a current-level skill, and optionally a conversational skill. A deterministic selector enforces prerequisites and eligibility. A model may help choose a natural topic or ordering within those bounds, but cannot grant mastery, waive prerequisites, or set the learner's level.

A Fluent plan contains a lightweight conversation focus rather than graded curriculum objectives. Both plan types pin their relevant versions and remain stable through retry or reconnect. A deleted or expired memory is excluded before call creation even if it was eligible when the plan was first drafted.

## 6. During a conversation

### Conversation flow

- The tutor begins with one approachable question about the learner's everyday life. Time since the last session, optional interests, and one safe current hook can make it specific.
- After an answer, the tutor briefly responds and proactively asks a relevant follow-up. It does not wait for the learner to invent every new topic.
- The tutor can work in the daily topic, requested words, and plan objectives through natural questions. It does not announce hidden objectives, repeat a fixed script, or force a topic the learner has left.
- If a topic stalls, the tutor pivots to a concrete question or a related everyday topic without making the silence awkward.
- If the learner asks for help, switches to the base language because they are stuck, or struggles to communicate, the tutor first gives the smallest useful scaffold and invites another target-language attempt. It resumes normal flow once the learner can continue.
- Most tutor turns are shorter than learner turns. The tutor asks one primary question at a time for Beginner and Intermediate learners.

### Language and pacing

The selected target language is the session's practice language. The selected base language is used only for brief clarification or scaffolding that helps the learner resume the target language. There is no application-wide default conversation language. Accent and voice delivery are configured for the selected target language separately from the language-switching rule.

Level controls sentence complexity, turn length, and model speaking cadence. The learner's pace preference and supported playback-rate setting adjust delivery without changing the assessed level. A request to slow down or speed up takes effect during the session.

### Corrections and pronunciation

The tutor corrects errors that block meaning with a short reformulation. It handles other errors according to correction preference and conversation flow. Pronunciation help is gentle and specific: when the audio supports a clear and useful observation, it points out one issue, models the word or phrase, and offers a retry. Beginner feedback concentrates on intelligibility; Intermediate and Advanced feedback may address a recurring or salient issue without interrupting every turn. Fluent receives pronunciation correction only when requested.

When audio is unclear, the tutor asks for repetition instead of asserting that the learner pronounced something incorrectly. It does not claim precise phoneme or accent diagnosis from uncertain live audio. The initial post-session evaluator can review transcript evidence that the tutor offered a correction and retry, but cannot judge acoustic accuracy from text. Pronunciation evidence affects progression only when an approved audio evidence and evaluator policy supports that claim.

## 7. After a session

For a usable Beginner, Intermediate, or Advanced session, post-session processing produces candidate objective evidence, vocabulary and concept observations, corrections, possible level evidence, a recap, and permitted personal insights. Every learning or assessment claim cites exact learner turns. Application rules validate candidates and determine progress and level. Model output never directly changes durable mastery or level.

The learning recap shows a concise summary, objective outcomes, a small number of useful corrections, next focus, and any level change with an understandable reason. It does not treat exposure or repetition alone as mastery. The next planning snapshot is committed only with validated state and a completed analysis run.

For a Fluent session, processing produces a brief conversation summary and candidate personal insights only. It does not create skill evidence, mastery changes, level advice, or a correction recap. The learner can still inspect and delete any retained insights.

A session with no usable learner turn does not produce learning progress. Analysis failure exposes a processing state and retry path; it does not block a later conversation.

## 8. Personal insights and memories

Memories help Mori ask relevant questions. They are separate from curriculum evidence and learning snapshots. Mori may retain only bounded, useful facts the learner explicitly volunteered, such as interests, preferred topics, broad context, or low-sensitivity upcoming events. It must not infer identity, beliefs, relationships, or emotional state from hints. Sensitive facts are not saved or proactively resurfaced.

Each memory has source session and turn references, confidence, creation time, expiry, sensitivity classification, and deletion state. A remembered event is not asserted as still current without confirmation. The learner can inspect and delete memories. Deletion prevents future prompt use; deleting a session also removes memories derived from it under the approved privacy workflow.

## 9. Product requirements

| ID | Priority | Requirement |
| --- | --- | --- |
| LS-01 | P0 | Require explicit, supported base and target language selection before plan creation or voice start. |
| LS-02 | P0 | Support the four levels and distinguish provisional self-selection from assessed learning level. |
| LS-03 | P0 | Offer optional, editable interests and optional per-session topic and requested words. |
| LS-04 | P0 | Create a versioned plan before each session; use one to three eligible objectives in learning mode and a conversation focus in Fluent mode. |
| LS-05 | P0 | Keep conversation moving with relevant questions and follow-ups while prioritizing help when the learner is stuck. |
| LS-06 | P0 | Speak primarily in the profile target language, with bounded base-language help, level-aware pace, and gentle pronunciation support. |
| LS-07 | P0 | Validate turn-grounded evidence and apply deterministic learning and level rules for Beginner through Advanced. |
| LS-08 | P0 | Produce only a brief conversation summary and permitted memories for Fluent practice mode. |
| LS-09 | P0 | Keep personal memories inspectable, deletable, bounded, and separate from learning evidence. |
| LS-10 | P0 | Use the last committed snapshot when newer analysis is pending; keep plans stable through retries and reconnects. |
| LS-11 | P0 | Make missing language, unsupported course, failed planning, uncertain audio, and analysis delay understandable to the learner. |

## 10. Acceptance and evaluation

1. An account without selected languages can load onboarding but cannot create a plan or connect a voice call. It can complete onboarding without an automatically selected language.
2. A first-session plan uses provisional placement and starter content. A later plan cites the last committed snapshot and excludes deleted or expired memories.
3. Representative plans across Beginner, Intermediate, and Advanced contain only eligible objectives with no more than three. Fluent plans contain a conversation focus and no graded curriculum objective.
4. In reviewed voice sessions, the tutor proactively opens, follows up, and recovers stalled topics. It helps a struggling learner before asking a new topic question.
5. Reviewed transcripts show target-language adherence, bounded base-language scaffolding, appropriate turn length, and whether tutor-offered pronunciation repair is gentle and appropriately uncertain. A separate live-call check validates connection and turn delivery; transcript review does not establish acoustic accuracy or speaking rate.
6. Accepted learning claims cite exact turns and follow deterministic rules. Replaying the same session and versions does not duplicate evidence, memories, recaps, or snapshots.
7. Fluent sessions show no learning advice or progress update and produce only a brief summary plus inspectable permitted memories.
8. Memory or session deletion prevents later resurfacing and triggers the approved derived-state rebuild where learning evidence is removed.

Evaluation fixtures must cover every level, new and returning learners, conflicting or stale memories, user-selected topics, requested words, unclear transcript spans, a learner performing above or below their recorded level, interrupted sessions, and Fluent practice. Product release requires agreed transcript-based thresholds for language adherence, scaffolding, tutor correction behavior, level calibration, memory safety, and extraction validity. Acoustic pronunciation quality and actual voice pacing need a later audio evaluation and are excluded from this gate.

## 11. Release dependencies

- Publish at least one supported language pair with an initial curriculum, starter objectives, voice policy, and level thresholds. The web may list planned languages, but unsupported pairs cannot start voice practice.
- Decide numerical assessment thresholds and evaluator pass criteria for each level.
- Approve the memory sensitivity and retention policy. Approve an audio evidence policy before using pronunciation to change progress or level.
- Reconcile the original MVP PRD and architecture documents with the four-level and explicit-language decisions before their affected implementation slices are marked complete.
- Validate the selected Realtime model, prompt versions, and extraction model with representative transcript reviews; validate voice connection and delivery in live calls. Acoustic quality evaluation is a later gate if it becomes a product claim.

# Mori learning system PRD

**Status:** Approved product contract for implementation

**Date:** September 26, 2026. Lesson progression revised October 5, 2026.

**Scope:** Onboarding inputs, level and practice mode, session planning, live tutor behavior, learning evidence, personal memory, recaps, and the next-session feedback loop.

This document is the product contract for Mori's learning system. It supersedes conflicting learning-specific requirements in [the original MVP PRD](PRD.md), particularly its fixed language pair, six-level framework, and Fluent learning behavior. Entitlements, session duration, authentication, and privacy workflows retain their existing approved contracts unless this document explicitly changes them. The companion implementation design will define APIs, persistence, runtime boundaries, and migration steps.

## 1. Product outcome

Mori helps a learner speak a chosen target language through an engaging voice conversation. For learners in learning mode, each session has one selected lesson that develops a conversational ability, with a small number of eligible supporting or review objectives. Validated evidence determines whether the learner repeats, reviews, or advances from that lesson. A Fluent learner can choose conversation practice without lessons, learning advice, or mastery tracking.

The tutor carries the conversation: it asks relevant questions about everyday life, responds to answers, asks follow-ups, and pivots when a topic runs out. It pauses that momentum when the learner asks for help or struggles to express an idea, then helps them retry. Objectives and personal context shape the conversation without turning it into a script.

## 2. Scope and boundaries

### In scope

- Explicit base and target language selection during onboarding.
- A provisional starting level and editable tutor preferences.
- Optional, editable interests and optional topic or words requested for an individual session.
- A versioned pre-session plan that selects a lesson for learning mode, and a level-aware Realtime tutor prompt.
- Proactive conversation, bounded support-language scaffolding, and gentle pronunciation help.
- Post-session evidence, deterministic learning progress, level assessment, recap, and safe personal memory for learning mode.
- A separate Fluent practice mode with a brief conversation summary and inspectable permitted memories.
- Recovery when analysis is delayed, a memory is deleted, or a session is interrupted.

### Outside this PRD

- Payment, entitlement quantities, authentication, and the 10-minute session cap.
- A specific provider model, voice, cloud region, or price.
- Full curriculum content and numerical assessment thresholds, which must be published and evaluated before release.
- Support for every target language shown in the web app through Mori's shared course. The base language for help is currently English.

## 3. Learner profile and onboarding

1. The learner explicitly selects a base language for help and a target language for practice. Neither field has a preselected value. The app shows the supported languages.
2. The learner selects an approximate starting level: Beginner, Intermediate, Advanced, or Fluent. They may choose "I'm not sure"; this creates a provisional Beginner placement for learning mode, not an assessed level.
3. The learner selects correction frequency and tutor pace. Existing defaults for these preferences may be offered, but no language can be inferred from them.
4. The learner may enter conversation interests. Interests are optional, editable, and are not treated as evidence of skill or as permission to save sensitive facts.
5. The learner can review the chosen languages, level or mode, and preferences before starting voice practice.

An account may exist without a language profile while onboarding is incomplete. The app must not create a plan or start a conversation until both languages are explicitly selected and supported. It directs the learner back to the missing onboarding step. A provisional level is not a verified assessment.

The language profile owns language-specific preferences, learning state, memories, and session history. Changing the target language starts or activates a separate profile; it does not reinterpret evidence or memories from another language.

The tutor uses Mori's shared course and conversation policy with the learner's selected base and target languages. Language selection is explicit; no target language is an application default.

## 4. Four-level framework

These are Mori product levels, not formal certifications.

| Level | Learner ability | Tutor behavior |
| --- | --- | --- |
| Beginner | Can handle basic introductions such as name and origin but cannot yet sustain a conversation about their life. | Short predictable target-language exchanges, one question at a time, substantial base-language explanation early on, and supportive retries. |
| Intermediate | Can hold a basic conversation about familiar everyday topics. | Clear connected sentences, follow-up questions, and targeted help when blocked. |
| Advanced | Can handle more complex or abstract conversation. | Mostly natural pace and register, nuanced follow-ups, and selective feedback. |
| Fluent | Primarily wants natural conversation practice. | Natural conversation without unsolicited teaching, learning advice, or mastery tracking. |

There is no separate zero-knowledge tier. Beginner is the lowest product level.

For Beginner through Advanced, self-selection is provisional until a usable diagnostic conversation provides enough evidence. Later promotion or demotion follows published, versioned rules and evidence from valid learner turns. A short, low-quality, or failed session cannot change an assessed level. Changes are explained in plain language.

Fluent selection is a **practice-mode choice**, not a claim that Mori has verified fluency. It takes effect immediately so a learner who wants only practice does not receive an unwanted diagnostic or learning advice. The learner can switch into assessed learning mode later, which starts with a diagnostic. Mori does not silently move someone into or out of Fluent practice mode.

### Lesson progression

Learning mode uses one ordered, versioned ten-lesson conversation course shared across supported target languages and learning levels. Fluent practice mode has no lesson sequence. The lesson count does not fix the number of sessions. The tutor gives examples and speaking help in the learner's selected languages. A learner may need several sessions to demonstrate one lesson, return to an earlier lesson for review, or move ahead after supported placement evidence. Progress remains separate for each language profile even though the lesson sequence is shared. A diagnostic can be woven into a lesson; it must not become a separate lesson that repeats indefinitely while assessment is pending.

The Beginner sequence develops these conversational abilities:

| Lessons | Focus |
| --- | --- |
| 1 | Expand beyond name and origin: say where one lives and describe work, study, or another basic part of daily life. Introduce a phrase for saying one is learning the target language when helpful. |
| 2 | Build on lesson 1: describe an interest or familiar activity, add a related detail, respond to a follow-up, and help keep the exchange going. Introduce a phrase for asking what something means when helpful. |
| 3–4 | Talk about routines and familiar recurring activities. |
| 5 | Respond to unexpected but relevant follow-ups. |
| 6–7 | Complete practical exchanges. Food is a default scenario; the learner may request another exchange such as shopping, a cinema visit, or talking with a relative. |
| 8 | Recover when an utterance is not understood, including clarification and describing around a missing word. |
| 9 | Describe a recent event or an upcoming plan. |
| 10 | Sustain a mixed, guided conversation for approximately seven minutes within the ten-minute session. |

Each blueprint states the capability, suggested conversational territory, support and difficulty guidance, and what independent learner behavior would provide evidence. It does not prescribe an ordered question script or exact learner answers. Optional model phrases for learning or clarification are examples, not a vocabulary test. The tutor follows the learner's meaning, varies follow-ups and scenarios, and keeps the conversation moving.

The [lesson 1 and 2 tutor guidance draft](prompts/beginner-lessons-1-2.md) separates these first two capabilities and their proposed evidence criteria. It is a review draft, not published lesson-profile content.

If a Beginner or an "I'm not sure" learner cannot yet handle name and origin, Mori supplies those basics within lesson 1 and keeps the task approachable. Completing the last lesson of a level supplies assessment evidence but does not automatically change the assessed level. Until a level change is supported, the planner can use review and harder variations of demonstrated lessons without repeating an identical conversation.

## 5. Before a session

The learner can see a suggested focus and optionally enter a topic or words they want to use. Leaving these fields blank is valid. The app explains that Mori will help them continue in the target language when they get stuck.

For learning mode, Mori creates a plan before connecting audio from:

- The selected language profile, provisional or assessed level, and level confidence.
- The last committed learning snapshot, including lesson outcomes and prior difficulties, if one exists.
- Published curriculum gates, due review items, and recent supported repair needs.
- Correction and pace preferences.
- Optional interests, a session topic, and requested words.
- Current, safe conversation hooks and memories, with freshness and expiry.
- Time since the last completed session and the session time budget.

The first session has no learning snapshot. It uses provisional placement and the first lesson for that level, with placement evidence gathered during conversation. If the previous session's analysis is pending or failed, the next plan uses the last committed snapshot rather than assuming the lesson was passed. Personal memories are separate from learning evidence and are never treated as proof of ability.

A learning-mode plan pins exactly one lesson from Mori's shared course and its version, and one to three eligible objectives, normally the lesson's primary capability plus an appropriate review or repair goal. A deterministic selector uses the learner's language profile, learning level, and last committed lesson state to choose the lesson. It marks the encounter as first, continuation, or review using prior usable sessions with that lesson. Continuation does not imply failure: the prior analysis may still be pending or may have found insufficient evidence. The selector enforces prerequisites and eligibility. A model may help choose a natural topic or ordering within those bounds, but cannot choose the lesson, grant a pass, waive prerequisites, or set the learner's level. User-requested topics and scenarios can change the conversation setting without changing the lesson's capability or assessment target.

A Fluent plan contains a lightweight conversation focus rather than graded curriculum objectives. Both plan types pin their relevant versions and remain stable through retry or reconnect. A deleted or expired memory is excluded before call creation even if it was eligible when the plan was first drafted.

## 6. During a conversation

### Conversation flow

- The tutor briefly frames the selected lesson, then begins with an approachable invitation or question suited to it. Time since the last session, optional interests, and one safe current hook can make it specific.
- After an answer, the tutor briefly responds and proactively asks a relevant follow-up. It does not wait for the learner to invent every new topic.
- The tutor works the lesson capability, requested topic or scenario, and review objectives into natural questions. It does not follow a fixed question template, announce an assessment checklist, or force a topic the learner has left.
- If a topic stalls, the tutor pivots to a concrete question or a related everyday topic without making the silence awkward.
- If the learner asks for help, switches to the base language because they are stuck, or struggles to communicate, the tutor first gives the smallest useful scaffold and invites another target-language attempt. It resumes normal flow once the learner can continue.
- Most tutor turns are shorter than learner turns. The tutor asks one primary question at a time for Beginner and Intermediate learners.

### Language and pacing

The selected target language is the session's practice language. In early Beginner lessons, the tutor may use mostly the selected base language to explain new words, phrases, and the immediate task, then create short target-language speaking opportunities. As the learner demonstrates comprehension, the tutor increases target-language conversation and reduces repeated explanation. Intermediate and Advanced use the base language mainly for concise help; Fluent uses it only when requested. There is no application-wide default conversation language. Accent and voice delivery are configured for the selected target language separately from the language-switching rule.

Level controls sentence complexity, turn length, and model speaking cadence. The learner's pace preference and supported playback-rate setting adjust delivery without changing the assessed level. A request to slow down or speed up takes effect during the session.

### Corrections and pronunciation

The tutor corrects errors that block meaning with a short reformulation. It handles other errors according to correction preference and conversation flow. Pronunciation help is gentle and specific: when the audio supports a clear and useful observation, it points out one issue, models the word or phrase, and offers a retry. Beginner feedback concentrates on intelligibility; Intermediate and Advanced feedback may address a recurring or salient issue without interrupting every turn. Fluent receives pronunciation correction only when requested.

When audio is unclear, the tutor asks for repetition instead of asserting that the learner pronounced something incorrectly. It does not claim precise phoneme or accent diagnosis from uncertain live audio. The initial post-session evaluator can review transcript evidence that the tutor offered a correction and retry, but cannot judge acoustic accuracy from text. Pronunciation evidence affects progression only when an approved audio evidence and evaluator policy supports that claim.

## 7. After a session

For a usable Beginner, Intermediate, or Advanced session, post-session processing produces candidate lesson and objective evidence, vocabulary and concept observations, corrections, possible level evidence, a recap, and permitted personal insights. Every learning or assessment claim cites exact learner turns. Application rules validate candidates and determine progress and level. Model output never directly changes durable lesson completion, mastery, or level. A lesson outcome is demonstrated, needs practice, or insufficient evidence. Passage requires independent use across varied opportunities relevant to that lesson; copying a supplied phrase or merely hearing it is insufficient. Retry guidance identifies the observed difficulty without treating it as a permanent learner trait.

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
| LS-04 | P0 | Create a versioned plan before each session; pin one selected lesson and one to three eligible objectives in learning mode, or a conversation focus without a lesson in Fluent mode. |
| LS-05 | P0 | Keep conversation moving with relevant questions and follow-ups while prioritizing help when the learner is stuck. |
| LS-06 | P0 | Use the target language for speaking practice, substantial base-language explanation in early Beginner lessons, less support as ability grows, level-aware pace, and gentle pronunciation support. |
| LS-07 | P0 | Validate turn-grounded evidence and apply deterministic lesson, item, and level rules for Beginner through Advanced. |
| LS-08 | P0 | Produce only a brief conversation summary and permitted memories for Fluent practice mode. |
| LS-09 | P0 | Keep personal memories inspectable, deletable, bounded, and separate from learning evidence. |
| LS-10 | P0 | Use the last committed snapshot when newer analysis is pending; keep plans stable through retries and reconnects. |
| LS-11 | P0 | Make missing language, unsupported course, failed planning, uncertain audio, and analysis delay understandable to the learner. |

## 10. Acceptance and evaluation

1. An account without selected languages can load onboarding but cannot create a plan or connect a voice call. It can complete onboarding without an automatically selected language.
2. A first-session plan uses provisional placement and the first lesson for that level. A later plan cites the last committed snapshot, selects a first, continuation, or review encounter using prior usable lesson sessions, and excludes deleted or expired memories. Session count alone never advances a lesson.
3. Representative plans across Beginner, Intermediate, and Advanced pin one published lesson and contain only eligible objectives with no more than three. Fluent plans contain a conversation focus and no lesson or graded curriculum objective.
4. In reviewed voice sessions, the tutor proactively opens, follows up, and recovers stalled topics. It helps a struggling learner before asking a new topic question.
5. Reviewed transcripts show substantial, useful base-language explanation in early Beginner lessons, increasing target-language participation, appropriate turn length, and whether tutor-offered pronunciation repair is gentle and appropriately uncertain. They show flexible lesson guidance without a repeated question script. A separate live-call check validates connection and turn delivery; transcript review does not establish acoustic accuracy or speaking rate.
6. Accepted lesson passes and learning claims cite exact turns and follow deterministic rules. Replaying the same session and versions does not duplicate evidence, lesson decisions, memories, recaps, or snapshots. Insufficient evidence leaves progression unchanged.
7. Fluent sessions show no learning advice or progress update and produce only a brief summary plus inspectable permitted memories.
8. Memory or session deletion prevents later resurfacing and triggers the approved derived-state rebuild where learning evidence is removed.
9. Beginner lessons 6–7 retain their practical-exchange capability when a learner chooses food, shopping, cinema, or another suitable scenario. The tutor varies questions and reactions instead of replaying a fixed exchange.
10. Beginner lesson 10 is evaluated on approximately seven minutes of mixed, guided conversation within the session. A short or interrupted session cannot be marked demonstrated solely because planned topics were mentioned.

Evaluation fixtures must cover every level, new and returning learners, conflicting or stale memories, user-selected topics, requested words, unclear transcript spans, a learner performing above or below their recorded level, interrupted sessions, and Fluent practice. Product release requires agreed transcript-based thresholds for language adherence, scaffolding, tutor correction behavior, level calibration, memory safety, and extraction validity. Acoustic pronunciation quality and actual voice pacing need a later audio evaluation and are excluded from this gate.

## 11. Release dependencies

- Publish Mori's shared course with supported language choices, lesson objectives, and level thresholds. Unsupported languages cannot start voice practice.
- Decide numerical assessment thresholds and evaluator pass criteria for each level.
- Approve the memory sensitivity and retention policy. Approve an audio evidence policy before using pronunciation to change progress or level.
- Reconcile the original MVP PRD and architecture documents with the four-level and explicit-language decisions before their affected implementation slices are marked complete.
- Validate the selected Realtime model, prompt versions, and extraction model with representative transcript reviews; validate voice connection and delivery in live calls. Acoustic quality evaluation is a later gate if it becomes a product claim.

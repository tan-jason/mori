# Personalized Mandarin Conversation Coach - MVP PRD

**Status:** Draft 0.3

**Date:** September 1, 2026

**MVP language pair:** English base language -> Standard Mandarin target language

## 1. Product summary

The product is a personalized, voice-first Mandarin learning app. A learner has natural conversations with an AI tutor that remembers their progress, adapts to their ability, revisits useful topics from their life, and deliberately practices a small number of learning objectives in each session.

The MVP is not an open-ended AI companion with language-learning flavor. It is a structured learning system delivered through natural conversation. The curriculum engine decides what the learner needs to demonstrate. The conversation model decides how to weave those objectives into an engaging discussion.

Sessions may end at any time and are capped at 20 minutes. During a session, Mandarin is the persistent default. When a learner asks for help, switches to English because they are stuck, or communicates unclear intent, the tutor may use brief English clarification and compassionate word-by-word or phrase-by-phrase scaffolding before returning to Mandarin. After each session, a separate analysis process extracts evidence, updates learning progress, assesses level, and prepares safe follow-up topics for the next conversation.

## 2. Problem

Traditional language apps provide structure but little realistic speaking practice. General-purpose voice assistants provide conversation but do not reliably remember learning progress, revisit weak skills, or apply consistent advancement criteria.

Learners need:

- A low-friction way to speak Mandarin regularly.
- Conversations relevant to their actual life.
- Speech and vocabulary appropriate for their current ability.
- Evidence-based tracking of what they have practiced and retained.
- A progression system that is consistent across sessions.
- Immersion without losing access to concise English help when needed.

## 3. Product principles

1. **Conversation first:** The experience should feel like a good conversation, not a spoken quiz.
2. **Learning is evidence-based:** Exposure to a word is not the same as learning it.
3. **Personalization has boundaries:** Remember useful context, but avoid invasive questions and sensitive-memory surprises.
4. **Immersion is supportive:** Mandarin is the default and persistent conversation language. Brief English help should remove a blocker and return the learner to speaking Mandarin.
5. **The LLM does not own progression:** Models propose plans and observations. Deterministic product logic validates and commits progress.
6. **Levels should be stable but reversible:** Promotion and demotion are possible, but neither should happen from a single ambiguous performance.
7. **Short sessions still count:** Ending early must preserve the transcript and any valid learning evidence.

## 4. Goals and non-goals

### 4.1 MVP goals

- Present visible base- and learning-language selectors fixed to English and Standard Mandarin for the MVP.
- Let an English-speaking learner hold a realtime voice conversation in Mandarin.
- Generate a personalized plan of one to three learning objectives before each session.
- Adjust vocabulary, sentence complexity, turn length, repetition, and speaking pace to the learner's level.
- Ask relevant general-life questions based on elapsed time and prior conversations.
- Track vocabulary, language concepts, curriculum competencies, and demonstrated retention.
- Assign one of six product levels: Beginner, Learning Beginner, Intermediate, Conversational, Advanced, or Fluent.
- Promote or demote a learner using transcript-grounded evidence and stable rules.
- Produce a useful session recap and seed appropriate topics for the next session.
- Enforce a 20-minute hard cap while allowing early ending.

### 4.2 Non-goals for MVP

- Language pairs other than English -> Mandarin.
- Cantonese, regional Chinese varieties, or translation among arbitrary languages.
- Formal HSK or CEFR certification.
- Reading-first courses, handwriting recognition, or essay correction.
- Human tutoring, social features, leaderboards, or classrooms.
- A broad AI companion intended to replace human relationships.
- Native-equivalence claims based only on app conversations.
- Fully generative curriculum progression with no predefined competency map.

## 5. Target user

The initial user is an adult English speaker who wants regular Mandarin speaking practice and is comfortable talking to an AI tutor for 5 to 20 minutes at a time.

MVP assumptions:

- Beta access is limited to users aged 18 or older.
- The learner's base language is English.
- The target variety is Standard Mandarin with a consistent Putonghua-oriented pronunciation.
- Simplified Chinese is used in written learning records. Pinyin may be displayed as support but is not treated as another language.
- The learner has a microphone and a reliable internet connection.

## 6. Definitions

- **Learning objective:** A session-specific behavior the learner should practice or demonstrate.
- **Curriculum item:** A durable vocabulary, grammar, listening, interaction, pronunciation, or discourse competency.
- **Evidence:** A transcript-grounded observation tied to exact session turns.
- **Learned item:** An item demonstrated successfully across enough distinct opportunities to meet its retention rule.
- **Conversation hook:** A short-lived, non-sensitive topic from a prior session that may be revisited naturally.
- **Language profile:** All progress, memories, and settings associated with one base-target language pair.
- **Full session:** A session with at least five minutes of connected conversation or enough evidence to complete the planned diagnostic.

## 7. Core user experience

### 7.1 Onboarding

The learner:

1. Creates an account and accepts microphone, transcript, and personalization disclosures.
2. Reviews two labeled dropdowns: Base language is preselected to English, and Language to learn is preselected to Standard Mandarin. Both controls are disabled in the MVP and explain that more language pairs are planned.
3. Selects an approximate starting ability or chooses "I'm not sure." Choosing "I'm not sure" initializes the provisional level to Beginner.
4. Selects correction preference: light, balanced, or frequent. Balanced is the default.
5. Completes a short conversational diagnostic inside the first session.
6. Receives an initial level and a plain-language explanation of what that level means.

The initial level may change after the first diagnostic. Beginner fallback and any self-selected level are provisional and are never treated as verified evidence.

### 7.2 Home screen

The home screen shows:

- Current level and a short description.
- Start conversation button.
- Suggested session focus, such as "talking about this week" or "practicing past events."
- Due review count.
- Recent learning items and session history.
- Controls to view or delete remembered information.

Before every session, the interface reinforces the learner's role: "Always try your best to speak Mandarin. If you do not know a word, use the Mandarin you already know to describe what you mean. Your tutor will help you build the missing word or phrase without judgment."

### 7.3 Pre-session planning

Before connecting audio, the session orchestrator creates a plan using:

- Current level and confidence.
- Required curriculum gates for the current level.
- Items due for spaced review.
- Recent mistakes or uncertain evidence.
- Recent conversation hooks and their expiry dates.
- Time since the last completed session.
- Learner correction and speed preferences.
- The 20-minute time budget.

Each plan contains no more than three objectives:

1. One retention or repair objective.
2. One current-level or next-step curriculum objective.
3. Optionally, one conversational objective such as asking a follow-up question or narrating a past event.

A deterministic selector chooses the curriculum items. An optional planning LLM may choose the conversational theme, ordering, and natural prompts, but may not unlock content, waive gates, or change the learner's level.

### 7.4 Session shape

The tutor uses this flexible structure:

| Approximate time | Purpose |
| --- | --- |
| 0:00-2:00 | Greeting, audio calibration, and life check-in |
| 2:00-6:00 | Warm-up and review of a prior item |
| 6:00-14:00 | Main conversation with current objectives |
| 14:00-18:30 | Follow-up, repair, or a second attempt |
| 18:30-20:00 | Natural wrap-up and one brief learner reflection |

This is guidance, not a script. The learner may change the subject, ask for help, or end at any time. The tutor should not announce hidden objectives or force completion when the conversation naturally goes elsewhere.

### 7.5 Proactive life questions

The opening should respond to elapsed time in the learner's local timezone:

| Time since last conversation | Opening strategy |
| --- | --- |
| No prior session | Ask what motivated them to learn Mandarin and what is happening in their life now |
| Under 24 hours | Ask what has happened since the last conversation |
| 1-6 days | Ask about their week or a recent event |
| 7-27 days | Ask what has been happening lately and whether a prior topic changed |
| 28+ days | Acknowledge the gap without guilt and ask what they are focused on now |

All questions are spoken in Mandarin. The tutor may use one relevant conversation hook, but must not:

- Pretend certainty about an event that may have changed.
- Mention a sensitive fact unexpectedly.
- Pressure the learner to discuss health, finances, relationships, work conflict, politics, religion, or trauma.
- Ask the same generic question every session when a better safe hook exists.
- Shame the learner for missing sessions.

### 7.6 Ending a session

The learner may end through a visible End button or a clear spoken request in English or Mandarin.

- At 18:30, the tutor begins steering toward closure.
- At 19:00, the interface shows a one-minute warning.
- At 19:45, the tutor may finish only the current short thought.
- At 20:00, the client stops new model output, closes the call, and marks the reason as `time_limit`.
- The hard cap is 20 minutes of connected session time measured by the server, not by model judgment.
- Early, dropped, and time-limited sessions all enter post-session processing if they contain at least one usable turn.

If the connection drops, the app offers a short reconnect window. Connected time already used still counts toward the 20-minute cap.

### 7.7 Post-session recap

The recap appears when processing finishes and contains:

- A short summary of what was discussed.
- Objectives attempted and demonstrated.
- New, strengthened, and due-for-review words or concepts.
- Up to three high-value corrections with examples.
- Current level and any level change with a concise reason.
- A preview of likely next-session focus.

The recap interface may use English for clarity. The Mandarin-first spoken-language policy applies to the live tutor's audio. Mandarin examples should include characters and optional pinyin.

## 8. Live tutor behavior

### 8.1 Language policy

The tutor uses Mandarin by default and English only as a brief, targeted scaffold that helps the learner resume Mandarin.

| Learner behavior | Tutor response |
| --- | --- |
| Normal conversation in Mandarin | Respond in Mandarin |
| Learner switches to English or appears stuck | Respond with compassion. Help reconstruct the idea word by word or phrase by phrase using Mandarin the learner already knows, give a concise English meaning when needed, and invite a new attempt in Mandarin |
| Learner explicitly asks what a Mandarin word or phrase means, or asks for its English translation | Give a concise English definition or translation, show how the word or phrase fits the learner's intended sentence, and invite the learner to try it in Mandarin |
| Learner asks for a broad grammar lesson or correction explanation in English | Keep practice centered on Mandarin, but use concise English to resolve the blocking concept before demonstrating it in Mandarin and inviting a retry |
| Learner asks the tutor to continue the conversation in English | Acknowledge the request compassionately, explain briefly in English that the session will return to Mandarin, then offer enough word-by-word or phrase-by-phrase support for the learner to continue |
| Learner requests a third language | Explain briefly that the MVP supports only English and Mandarin, then resume Mandarin practice |
| Model is uncertain what English help the learner needs | Ask a short clarification in English, then provide the smallest useful scaffold |

English help is bounded by the learner's immediate need rather than a rigid one-response limit. It may span the short exchange needed to identify the blocker, explain it, and help reconstruct an utterance. It must end once the learner can continue, and a broad request to speak English never changes the session default. English scaffolding must not expand into unrelated teaching, long preambles, or English small talk.

The tutor reinforces productive effort without shame: try to express the idea with the Mandarin already available, accept imperfect attempts, and provide the smallest compassionate scaffold that unlocks the next Mandarin attempt.

The system prompt must separately pin conversation language, exception rules, accent, and pacing. Language compliance must be measured at the emitted audio transcript level, not assumed from the prompt.

### 8.2 Level-adaptive speech

Speaking pace is controlled through both model pacing instructions and supported playback-rate configuration. Playback rate alone is insufficient because sentence shape, pauses, and cadence also affect comprehension.

| Level | Default tutor behavior | Initial playback target* |
| --- | --- | --- |
| Beginner | Very short clauses, common words, frequent pauses, one question at a time, repetition without pressure | 0.75x |
| Learning Beginner | Short sentences, predictable structures, limited new vocabulary, deliberate pauses | 0.82x |
| Intermediate | Connected sentences, natural but clear cadence, occasional paraphrase | 0.90x |
| Conversational | Mostly natural turns, moderate idiom use, less repetition | 0.97x |
| Advanced | Natural speed and complexity, nuanced follow-ups | 1.00x |
| Fluent | Fully natural pacing and register with no artificial simplification | 1.03x |

\*Targets are product starting points and must be tuned through comprehension testing and model evaluation.

The learner can ask the tutor to slow down or speed up at any time. The change applies immediately for the remainder of the session. An explicit persistent preference may shift future defaults within safe bounds, but it does not change the learner's assessed level.

### 8.3 Turn-taking

Use [OpenAI Realtime conversation capabilities](https://developers.openai.com/api/docs/guides/realtime-conversations) and configuration for the first five behaviors rather than building a separate audio turn system. Realtime provides voice activity detection, speech-start and speech-stop events, automatic response interruption, response cancellation, and conversation-item truncation. Input transcription confidence signals may be enabled to support uncertainty handling, while session instructions control response length. The final two behaviors remain explicit tutor-policy instructions.

- Use Realtime voice activity detection for natural turn boundaries and interruption.
- When the learner barges in, use native interruption events, stop client playback immediately, and truncate unplayed tutor audio from conversation state.
- Combine Realtime speech state with input-transcription quality signals and client-side gating so background speech is not answered confidently.
- Ask for repetition when transcription confidence or intent confidence is low.
- Configure the Realtime session to keep most tutor turns shorter than the learner's turns.
- Ask one primary question per turn at Beginner through Intermediate levels.
- Avoid monologues, excessive praise, and repeated filler.

### 8.4 Corrections

- Correct errors that block meaning immediately with a short Mandarin reformulation.
- For non-blocking errors, prioritize conversation flow and correct selectively according to the learner's preference.
- Give the learner a natural second attempt when it advances an objective.
- Do not claim pronunciation precision beyond available audio evidence.
- Do not interrupt every sentence or expose hidden scoring.
- English correction explanations stay concise and address an immediate blocker. The tutor then demonstrates the correction in Mandarin and invites another attempt.

## 9. Curriculum and learning state

### 9.1 Curriculum model

The MVP curriculum is a versioned, curated competency graph. Items may depend on other items and may be tagged by:

- Level.
- Skill type: vocabulary, grammar, listening, pronunciation, interaction, or discourse.
- Topic domain.
- Prerequisites.
- Required evidence type.
- Review interval policy.
- Whether the item is a promotion gate.

Development cost is not a reason to let a model invent this graph dynamically. The graph is product content and must be testable, versioned, and migratable.

### 9.2 Learning states

Each learner-item pair moves through:

`unseen -> introduced -> practiced -> demonstrated -> retained`

- **Introduced:** The tutor used or explained the item.
- **Practiced:** The learner attempted it with support.
- **Demonstrated:** The learner used or understood it correctly in a qualifying opportunity.
- **Retained:** The learner demonstrated it again in a later session after the minimum review interval.

An item is shown as "learned" to the user only at `retained`. A model may propose a transition, but application logic verifies evidence count, distinct sessions, timing, confidence, and prerequisites.

Incorrect or uncertain use may lower mastery confidence and schedule review. It does not erase prior evidence. Mastery is a history, not a single boolean.

### 9.3 Vocabulary records

Vocabulary entries include:

- Canonical simplified characters.
- Pinyin with tone marks.
- Concise English sense used in context.
- Part of speech or phrase type.
- Example from or adapted from the session.
- Evidence turn IDs.
- Current learning state and confidence.
- First seen, last practiced, and next review timestamps.
- Common-error notes, if supported by evidence.

Polysemous words are tracked by sense. Saying one meaning of a word does not imply mastery of all meanings.

### 9.4 Grammar and conversational concepts

Concepts include grammar patterns, listening distinctions, pronunciation targets, interaction strategies, and discourse skills. Examples include asking a follow-up question, narrating a past event coherently, using a repair phrase, or distinguishing two commonly confused sounds.

## 10. Level framework

These are internal product levels, not formal certifications.

| Level | Working definition |
| --- | --- |
| Beginner | Recognizes or produces a small set of isolated words and rehearsed phrases; needs extensive scaffolding |
| Learning Beginner | Handles short, predictable exchanges about familiar needs using simple sentence patterns |
| Intermediate | Sustains everyday topics with linked sentences, asks and answers follow-ups, and repairs some breakdowns |
| Conversational | Maintains unscripted everyday conversation, paraphrases around gaps, and understands mostly natural speech |
| Advanced | Discusses abstract or complex topics with control, nuance, and flexible vocabulary despite occasional errors |
| Fluent | Communicates spontaneously and precisely across familiar and unfamiliar topics at natural speed; this is not a native-speaker claim |

### 10.1 Assessment dimensions

Every assessment scores transcript-grounded evidence for:

1. Listening comprehension.
2. Spoken interaction and turn management.
3. Vocabulary range and retrieval.
4. Grammar and sentence control.
5. Pronunciation and intelligibility, only where audio evidence supports it.
6. Discourse complexity and ability to repair gaps.

The overall level is not a simple average that can hide a critical weakness. Each level defines minimum thresholds by dimension plus required curriculum gates.

### 10.2 Promotion rules

After initial placement, promotion requires:

- Required promotion gates for the current level are retained or otherwise satisfied.
- Minimum thresholds are met in every critical dimension.
- Qualifying evidence appears in at least two of the three most recent full sessions.
- At least one qualifying performance is spontaneous rather than direct repetition.
- No unresolved high-confidence evidence places the learner below the target level.

### 10.3 Demotion rules

Demotion is allowed when:

- Two consecutive full sessions contain high-confidence evidence below the current level's lower bound, or
- A new-user diagnostic shows that the self-selected starting level was too high.

The system should normally demote by one level at a time. A large initial placement correction may move more than one level. A short, technical-failure-heavy, or low-transcript-confidence session cannot trigger demotion.

### 10.4 Stability and explainability

- Store the level, confidence, dimension scores, rule version, and evidence IDs for every assessment.
- Display level changes with a plain-language reason.
- Never tell the learner that a model's intuition is the reason.
- A user may request reassessment but cannot directly mark curriculum gates complete.
- Curriculum and assessment rule changes require versioned migrations and regression evaluation.

## 11. Post-session processing

### 11.1 Pipeline

```text
Realtime transcript + session plan + prior learner snapshot
                         |
                         v
               Structured LLM extraction
                         |
                         v
        Schema, provenance, and confidence validation
                         |
                         v
     Deterministic curriculum and level rule evaluation
                         |
                         v
       Transactional learner-state and recap update
```

### 11.2 Extractor output

The analyzer returns schema-constrained candidate data:

- Session summary.
- Objective evidence with exact turn references.
- Vocabulary and concept candidates.
- Correct and incorrect learner examples.
- Dimension-level assessment evidence.
- Candidate personal facts explicitly stated by the learner.
- Two or three safe future conversation hooks.
- Transcript quality and uncertainty flags.

### 11.3 Validation rules

- Every learning or assessment claim must cite one or more transcript turn IDs.
- New personal facts must be explicitly stated, not inferred.
- Candidate updates below the confidence threshold are stored as uncertain evidence or discarded.
- Vocabulary is normalized and deduplicated before insertion.
- State transitions must satisfy deterministic requirements.
- Level changes are computed outside the extraction model.
- Processing is idempotent by session ID and analyzer version.
- Failed processing retries without blocking the next session. Until completion, the next plan uses the last committed learner snapshot.

### 11.4 Conversation memory

Memories are separated from learning records.

Allowed by default:

- Current hobbies and learning interests.
- Broad work or school context volunteered by the learner.
- Upcoming low-sensitivity events.
- Preferred conversation topics.

Do not proactively retain or resurface:

- Passwords, authentication data, precise financial data, government identifiers, or exact addresses.
- Health diagnoses, trauma, intimate details, or other highly sensitive facts.
- Claims about another person that are not needed for the learner's experience.
- Model inferences about identity, beliefs, relationships, or emotional state.

Each memory has source session, source turns, confidence, sensitivity class, created time, last used time, and expiry. Conversation hooks expire by default after 30 days unless refreshed. The user can inspect and delete memories.

## 12. Functional requirements

| ID | Priority | Requirement |
| --- | --- | --- |
| FR-1 | P0 | Show preselected, disabled English base-language and Standard Mandarin learning-language selectors, then create one active language profile per user |
| FR-2 | P0 | Default an unsure learner's provisional level to Beginner, complete an initial conversational placement, and assign one of six verified levels |
| FR-3 | P0 | Generate a versioned plan with one to three objectives before every session |
| FR-4 | P0 | Conduct low-latency, interruptible, speech-to-speech Mandarin conversation |
| FR-5 | P0 | Enforce Mandarin as the session default while permitting brief, compassionate English clarification and word-by-word or phrase-by-phrase scaffolding when the learner is stuck |
| FR-6 | P0 | Adapt pacing, complexity, turn length, and scaffolding by level |
| FR-7 | P0 | Allow immediate early ending and enforce the server-authoritative 20-minute cap |
| FR-8 | P0 | Persist ordered user and tutor transcript turns with timing and confidence metadata |
| FR-9 | P0 | Analyze any usable completed or interrupted session asynchronously |
| FR-10 | P0 | Track vocabulary and concepts through introduced, practiced, demonstrated, and retained states |
| FR-11 | P0 | Compute explainable promotion and demotion using versioned deterministic rules |
| FR-12 | P0 | Generate safe future conversation hooks from explicit transcript content |
| FR-13 | P0 | Let users view and delete session history and remembered personal information |
| FR-14 | P0 | Avoid storing raw audio by default; retain the transcript and derived records |
| FR-15 | P1 | Let users tune correction frequency and request slower or faster speech |
| FR-16 | P1 | Show due reviews and a post-session recap |
| FR-17 | P1 | Reconnect after a brief network interruption without resetting the time cap |
| FR-18 | P1 | Support account-level transcript export and deletion |

## 13. Language switching and deletion

MVP shows preselected language selectors but disables changes from the English to Standard Mandarin pair. The data model must support a future switch safely.

When target-language switching is introduced:

- A user may still have only one active target language.
- Switching requires a destructive-action screen that lists exactly what will be deleted.
- The user must confirm twice, including typing or selecting the new target language.
- Language-specific curriculum state, vocabulary, concepts, assessments, session transcripts, recaps, and conversation memories are permanently deleted.
- Account identity, billing, legal consent records, and language-agnostic accessibility settings remain.
- The deletion is queued transactionally, blocks new sessions until complete, and emits an auditable completion record.
- The product must not imply recovery is possible after the deletion window closes.

## 14. Technical approach

### 14.1 Realtime conversation

Use an OpenAI Realtime speech-to-speech session over WebRTC for the client experience. OpenAI recommends WebRTC for browser or mobile clients that connect directly to a Realtime model, and its voice-agent guidance identifies speech-to-speech sessions as the fit for natural, low-latency turn-taking and barge-in. The standard API key remains on the trusted server. The model identifier, voice, and playback tuning are runtime configuration, not hardcoded product behavior.

The session service provides:

- Authenticated session creation.
- A privacy-preserving stable safety identifier.
- Session plan and bounded learner context.
- Prompt and tool configuration.
- Server-authoritative start and stop timestamps.
- Transcript event ingestion.
- Forced hang-up at the product cap.

The OpenAI platform currently allows Realtime sessions longer than the product's 20-minute cap, so the application must enforce its own limit. Session properties can be updated during a call, which allows a learner's explicit speed request to take effect without reconnecting.

### 14.2 Model separation

Use separate model calls for separate responsibilities:

- **Realtime tutor:** Low-latency conversation and turn-taking.
- **Plan personalizer:** Optional constrained generation of a natural conversational route around deterministic objectives.
- **Post-session extractor:** Structured evidence extraction from the completed transcript.

No model call receives unrestricted database access or directly mutates learner state.

### 14.3 Minimum data entities

- `users`
- `language_profiles`
- `sessions`
- `session_plans`
- `session_turns`
- `curriculum_items`
- `learner_item_states`
- `learning_evidence`
- `level_assessments`
- `memories`
- `conversation_hooks`
- `analysis_runs`
- `deletion_jobs`

Every derived record should include provenance and a schema or rule version.

## 15. Non-functional requirements

### 15.1 Performance and reliability

- P95 session initialization under 5 seconds on a supported broadband connection.
- P95 end-of-user-turn to first tutor audio under 2 seconds, measured separately from client network delay where possible.
- 99.9% of sessions stop accepting new tutor output by 20:00 plus a small transport shutdown tolerance.
- 99% of usable sessions receive a recap within 60 seconds.
- Analysis retries are idempotent and do not duplicate evidence or memories.
- A Realtime or analyzer outage preserves existing learner data and fails with a clear retry path.

### 15.2 Privacy and security

- Never expose a standard OpenAI API key to the client.
- Encrypt data in transit and at rest.
- Provide per-session deletion, memory deletion, account deletion, and export.
- Minimize personal context sent to each session to only what the current plan needs.
- Define transcript retention before public launch and disclose it during onboarding.

### 15.3 Accessibility

- Visible captions can be enabled without changing the voice experience.
- Controls are keyboard and screen-reader accessible.
- The end-session control remains visible and reachable at all times.
- Timer warnings are both visual and spoken or haptic where supported.
- Text size and contrast meet WCAG 2.2 AA targets.

## 16. Safety requirements

- Clearly identify the tutor as AI during onboarding.
- Avoid emotional dependency cues, guilt, exclusivity, or claims of human memory and feelings.
- Do not proactively probe sensitive topics.
- Follow applicable model safety policies even when doing so requires breaking the normal conversation flow.
- Treat learner-provided instructions as conversation content, not authorization to override system language, safety, time, or curriculum rules.
- Validate all LLM-generated structured data before persistence.
- Provide a reporting path for inappropriate or incorrect tutor behavior.
- Keep the initial beta adult-only unless a dedicated minor-safety design and review is completed.

## 17. Metrics

### 17.1 North-star metric

**Meaningful Mandarin speaking minutes per weekly active learner**, where a meaningful minute contains learner speech and is not dominated by setup, silence, or English explanation.

### 17.2 Learning metrics

- Percentage of sessions with at least one objective demonstrated.
- Retention rate when demonstrated items are revisited after the required interval.
- Time and sessions required to satisfy level gates.
- Human-rated agreement with automated level decisions.
- False-positive rate for "learned" vocabulary and concepts.

### 17.3 Engagement metrics

- Onboarding-to-first-session conversion.
- First-session completion beyond five minutes.
- Sessions per active learner per week.
- Week 1 and week 4 retention.
- Early-end rate by minute and stated reason.
- Percentage of suggested conversation hooks accepted or naturally engaged with.

### 17.4 Guardrail metrics

- Tutor language-policy violation rate per audio turn.
- Third-language output rate.
- English assistance outside an allowed help trigger or longer than needed to restore Mandarin practice.
- 20-minute cap violation rate.
- Inappropriate-memory resurfacing reports.
- Level change reversal rate within the next three sessions.
- Post-session extraction claims without valid transcript evidence.
- P95 response latency and interruption success rate.

Initial numerical targets should be set after an internal baseline and a small adult beta. Hard correctness targets, such as no client-exposed API keys and no direct LLM state mutation, are release gates rather than optimization metrics.

## 18. Evaluation and QA plan

Before beta, create a repeatable evaluation set covering:

- All six levels and multiple voices or accents from English-speaking learners.
- Mandarin mistakes, English code-switching, and requests for third languages.
- Explicit English-help requests, English code-switching caused by confusion, and ambiguous requests that require a short English clarification.
- Background speech, silence, interruptions, and dropped connections.
- Learners who perform above or below their stored level.
- Sessions ending at 30 seconds, five minutes, 19:59, and 20:00.
- Sensitive topics and attempts to make the tutor retain them.
- Transcription errors involving tones, homophones, names, and code-switching.

Evaluate:

- Mandarin-default adherence and the relevance, brevity, and effectiveness of English scaffolding at the tutor transcript and audio-review levels.
- Objective adherence without conversational awkwardness.
- Speaking pace, sentence length, and comprehension by level.
- Accuracy and provenance of extracted learning evidence.
- Promotion and demotion calibration against expert human ratings.
- Memory usefulness, sensitivity, and expiry behavior.

Prompt, model, voice, curriculum, and assessment-rule changes must run against the same regression set before release.

## 19. MVP acceptance criteria

The MVP is ready for a controlled adult beta when:

1. A new learner sees preselected, disabled English and Standard Mandarin selectors, receives a provisional Beginner level when unsure, completes placement, and starts a Mandarin voice session.
2. Every session begins with a persisted plan containing one to three valid curriculum objectives.
3. The tutor speaks Mandarin by default, responds compassionately when a learner is stuck, uses only the brief English clarification or word-by-word or phrase-by-phrase scaffolding needed to unblock them, and then returns to Mandarin.
4. A learner can interrupt the tutor, request slower speech, and end immediately.
5. The server ends all sessions at the 20-minute cap even if the client timer is manipulated.
6. A partial session still produces a valid recap when enough transcript exists.
7. Post-session output contains turn-level evidence and cannot directly mutate state.
8. Vocabulary cannot become "learned" from exposure or one same-session repetition.
9. Level promotion and demotion follow the documented versioned rules and can be explained from stored evidence.
10. Users can inspect and delete their sessions and remembered information.
11. Raw audio is not retained by default, and no standard provider API key reaches the client.
12. The regression suite meets release thresholds for language-policy adherence, English-scaffolding quality, extraction accuracy, timing, and level calibration.

## 20. Recommended MVP decisions

- Use deterministic curriculum selection plus LLM conversation planning, not fully LLM-generated progression.
- Start with a responsive web app and WebRTC before native mobile clients.
- Use Standard Mandarin, simplified characters, and optional pinyin in text recaps.
- Keep live audio Mandarin-first while allowing brief, targeted English scaffolding during a blocker and broader English explanation in the post-session learning UI.
- Do not retain raw audio by default.
- Treat personal memory and learning evidence as separate systems.
- Limit each session to three objectives to preserve conversational quality.
- Require cross-session evidence before labeling an item learned or changing an established level.
- Launch adult-only until minor-specific safety and consent requirements are designed.

## 21. Open product decisions

These decisions do not block the PRD but should be resolved before implementation is complete:

1. Should captions be off by default to encourage listening, or on by default for accessibility?
2. Should pinyin appear automatically for Beginner users or only on tap?
3. How long should transcripts and non-learning conversation memories be retained by default?
4. Should users see the six level names prominently, or primarily see competency progress?
5. How much of the post-session recap should be English versus Mandarin at each level?
6. Which correction preference should placement select when the user skips that choice?
7. What reconnect grace period balances continuity, cost, and implementation complexity?
8. What internal expert rubric and reviewer pool will calibrate level decisions?
9. Will reminders be part of MVP, and if so, what frequency and quiet-hour controls apply?
10. What usage or subscription limit applies beyond the 20-minute per-session cap?

## 22. Official OpenAI implementation notes

- OpenAI's [voice-agent guide](https://developers.openai.com/api/docs/guides/voice-agents) distinguishes direct speech-to-speech sessions for natural, low-latency conversation from chained voice pipelines for more predictable workflows.
- OpenAI recommends [WebRTC for browser and mobile Realtime clients](https://developers.openai.com/api/docs/guides/realtime-webrtc), with standard API credentials kept on the trusted server.
- The [Realtime conversation guide](https://developers.openai.com/api/docs/guides/realtime-conversations) documents stateful sessions, runtime session updates, interruptions, transcripts, and a provider session maximum that is longer than this product's 20-minute limit.
- The [Realtime prompting guide](https://developers.openai.com/api/docs/guides/realtime-models-prompting) recommends explicit language constraints and notes that playback speed and model pacing instructions affect different parts of the listening experience.

These platform details are implementation guidance, not permanent product assumptions. Confirm model availability, pricing, rate limits, event schemas, and supported speed configuration against current official documentation during implementation.

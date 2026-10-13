# Beginner lessons 1 and 2: curriculum and extraction as one package

**Status:** Part 1 is implemented and verified. Part 2 remains a proposal for discussion; Decisions is the selected review/scoring provider, and user insights are a separate user-owned stream.

**Recommendation:** ship the lesson definitions, extraction contract, and progression rules together. Plan lesson 1 around four 10-minute sessions, while allowing accepted evidence to make it shorter or longer. Every continuation begins with targeted recall, then adds 1-5 useful items as time and observed support allow. Code selects the lesson and session focus; the tutor generates the conversation.

This document has two parts: the curriculum and session experience, followed by extraction, durable learnings, and deterministic lesson selection. Scope remains beginner lessons 1 and 2.

## Part 1: lesson and curriculum

### What changes in the lesson definition

Give each lesson one versioned definition containing its goal, ordered capabilities, permitted capability keys, and evidence requirements. The tutor compiler uses the goal and selected focus. The extractor uses those same capability definitions to interpret practice. The progression reducer uses the evidence requirements to accumulate progress. Do not maintain separate, manually synchronized definitions of success in tutor and extractor prompts.

| Field | Purpose |
| --- | --- |
| Lesson key and content version | Identify an immutable definition. Old plans continue to resolve their pinned version. |
| Goal | State what the learner can accomplish in a conversation. |
| Ordered capabilities | Describe the learning sequence without prescribing dialogue or questions. |
| Evidence requirements | Define qualifying outcomes, permitted support, opportunity variety, and later-session recall. |
| Suggested encounter count | Set a product pacing expectation. It never acts as a completion rule. |

Put the first two beginner definitions in [curriculum.py](../../apps/backend/src/mori/modules/curriculum/curriculum.py). Add their typed fields and validation in [curriculum/domain.py](../../apps/backend/src/mori/modules/curriculum/domain.py), and immutable lookup in [catalog.py](../../apps/backend/src/mori/modules/curriculum/catalog.py). This is primarily a curriculum-data change, with a small typed contract shared by the downstream components.

### Lesson goals, sequence, and progress

| Lesson | Goal | Sequence / things to learn | Progress to accumulate |
| --- | --- | --- | --- |
| 1. First two-way conversation | Share a familiar detail, answer a related question, and contribute a question or reaction that returns the turn. | Express one meaningful detail; understand and answer a related question; contribute a reciprocal move; reuse the repertoire with less support. | Specific language practiced; whether the meaning was communicated; support needed; later-session recall for the three capabilities. |
| 2. Keep a familiar conversation going | Connect details about a familiar subject and help develop the thread through a relevant follow-up. | Recall lesson-1 language; add a connected detail; connect ideas; respond to a follow-up; ask a follow-up or volunteer another contribution. | Reuse from lesson 1; connected contributions; response to a fresh follow-up; learner initiative across sessions. |

A simple help request is available throughout. Neither lesson requires exact phrases, prescribed disclosures, or a list of life facts. Broad or imagined details count. The tutor chooses natural phrasing appropriate to the selected target language.

### How many sessions for lesson 1

**Plan for four sessions, approximately 40 minutes in total.** This is the initial pacing design, not a research-derived completion estimate or a promise that every learner will finish in four calls.

| Suggested encounter | Focus | Recall and additions |
| --- | --- | --- |
| 1 | One meaningful personal message and a supported exchange. | Start with a small allowance; proposed initial maximum is two new items. |
| 2 | Recall the earlier language and respond to a related question. | Use prior language before hearing a model, then add material for the current focus. |
| 3 | Recall and return the turn. | Reuse earlier language and develop a reciprocal question or reaction. |
| 4 | Combine the repertoire in a fresh two-way exchange. | Use a mix of recent and older material with less support; extend only as useful. |

The selected focus can move earlier or later. A learner who already has the repertoire may qualify after two usable sessions, including later-session recall. Another learner may need six or more sessions. Neither reaching four sessions nor learning a certain number of words grants completion.

Track distinct usable encounters by lesson and language profile. A usable encounter contains accepted learner practice for that lesson. A reconnect within the same session, a duplicate analysis job, and a reanalysis are not extra encounters. Track created/connected calls separately so product usage is not confused with learning progress.

### The session cycle

| Stage | Experience | Responsibility |
| --- | --- | --- |
| Recall | Briefly explain that the first exchange reuses previous practice; ask a targeted question. | Code supplies selected prior items. The tutor creates a question that invites the needed language without supplying the answer. |
| Learn | Introduce useful new material one item at a time. | Code supplies a maximum within 1-5. The tutor chooses actual wording that serves the selected capability. |
| Combine | Use familiar and new material together in conversation. | The tutor responds to meaning and helps the learner contribute to the exchange. |
| Close | End with a brief account of what was practiced. | Server timing signals the close. Post-session analysis captures the durable evidence. |

A new item is one deliberately introduced reusable word, phrase/frame, or conversation move. It is not every unfamiliar word heard. A phrase taught as one chunk counts as one item; separately taught vocabulary counts separately. The allowance is a maximum. A session can spend its time practicing old material and add nothing.

### My recommendation for recall UX

**Signpost recall once, then make it conversational and productive.** The learner should understand why Mori is revisiting something and get an opportunity to produce the language before hearing it again. Keep the initial recall period short, roughly one to two minutes, and return relevant older material naturally later in the call.

Avoid making recall feel like Mori forgot the learner's personal facts. Ask for a meaningful use of the expression in a new exchange or a clearly framed replay. The thing being recalled is language, not a private biography.

For the housing example in the feedback, asking whether the learner is still at a supplied place often invites only a yes/no answer and supplies the content. It may check recognition, but it does not show recall of the expression for saying where they live. An openly framed question about where they live is more useful for productive recall, provided the question is understood. A short explanation that this is language practice resolves the otherwise odd repetition. These are UX comparisons for review, not examples to embed in the runtime prompt.

Choose questions based on the target capability. A question-back move needs a conversational opening for the learner to ask back; a detail frame needs an opportunity to express a detail. Do not expect one generic question to measure every skill. A normal understandable question is an opportunity, not an answer cue. A supplied sentence stem, translation answer, or full model is assistance and must be labeled accordingly.

Give the learner time to try, offer a small cue after difficulty, and model when necessary. After modelling, create another useful opportunity rather than immediately treating the repeated answer as independent recall. Do not announce pass/fail or repeatedly say "recall" before every question.

This recommendation follows the distinction between recognizing meaning and producing a form to express meaning. A small vocabulary experiment found productive retrieval particularly effective for productive knowledge; it does not establish the ideal Mori opening or question wording. [Yanagisawa: receptive and productive retrieval](https://www.jstage.jst.go.jp/article/katejournal/30/0/30_11/_article/-char/en). Reuse across sessions is also supported by [Kim and Webb's spaced-practice meta-analysis](https://onlinelibrary.wiley.com/doi/10.1111/lang.12479). The UX design above is my application of that evidence.

### What goes into the tutor prompt

The compiler receives a saved session plan and renders only its applicable blocks: selected goal/focus, actual recall items, and the new-item limit. First encounters omit the recall block. Code decides that; the prompt contains no historical-routing branches.

Use a short generic instruction to signpost prior practice, ask questions that elicit the supplied language before giving answers, and then develop the session focus with up to the supplied number of new items. The tutor chooses the topic, questions, and target-language phrasing. Do not add fictional conversations, scenario menus, or competing alternative instructions.

Actual previously practiced forms and their observed support are data, marked as untrusted context. The existing shared policy owns tone, base-language help, pace, corrections, and concise turns. Remove overlapping history-selection logic and unsupported assumptions of familiar introductory language when the saved session plan takes ownership of those decisions.

### How to send the wrap-up signal

**Use the existing server-side Realtime connection. No extra LLM call is needed to tell the tutor that time is running out.**

The current [supervisor](../../apps/backend/src/mori/modules/sessions/supervisor.py) renews its call lease and checks `hard_deadline_at` in its watch loop. It attaches to the same call over a sideband WebSocket. The implementation sends a small wrap-up instruction when approximately 90 seconds remain. Use the existing authoritative deadline for this slice rather than creating a second timer.

1. Compute remaining time in code from the active call deadline. Set a durable `wrap_up` control state once the threshold is reached.
2. Send a server-authored system message through `conversation.item.create`, telling Mori to stop introducing material, finish the current exchange, and close briefly. This is a small conversation-phase update; it preserves the original tutor instructions. Realtime supports adding system context during a conversation. [OpenAI Realtime client events](https://developers.openai.com/api/reference/resources/realtime/client-events)
3. Record the control item's stable ID and acknowledge delivery on the matching server item event. On an ambiguous send or sideband reattachment, retrieve the item before retrying. A socket write alone does not establish that the provider accepted it.
4. Let the next normal tutor turn follow the instruction. Do not interrupt learner speech or create a competing audio response at the threshold. The hard deadline still ends the call. If evaluations show silent calls need a proactive close, add an idle-only response trigger separately, with explicit response/audio state tracking.

The implementation adds a durable attempt-scoped control record and handles acknowledgment/retrieval/error events. Acknowledgment requires the matching item ID and exact stored system-message content. Requests are lease-fenced, use a bounded timeout and five-second backoff, and stop after twelve attempts. Unknown retrieval errors remain unconfirmed rather than causing blind recreation. Control messages stay out of learner/tutor practice evidence.

A sideband reattachment to the same provider call does not reset the deadline or repeat an acknowledged instruction. Any future replacement call must use the session's remaining budget and inherit its wrap-up phase. The current call deadline is established during setup, so the product should not describe it as precisely ten minutes of learner speech. Changing that clock's starting point is a separate decision. [OpenAI server-side controls](https://developers.openai.com/api/docs/guides/voice-server-controls)

### Components for part 1

| Component | Responsibility |
| --- | --- |
| `curriculum.py`, `curriculum/domain.py`, `catalog.py` | Publish the two beginner lesson definitions and their common evidence contract. |
| `sessions/prompt.py` | Compile a selected session plan into concise applicable tutor instructions. |
| `sessions/supervisor.py`, `sessions/models.py` | Deliver and track the timed wrap-up control through the existing sideband. |

The choice of what history to include and which lesson to select belongs to part 2. Static curriculum data does not need access to a learner's transcripts or database.

### Implemented Part 1 and verification

The current publication is `mori-framework-v2`, with beginner lesson definitions under `beginner-conversation-v1` and tutor policy `mori-framework-v5`. The historical `mori-framework` course remains resolvable. Beginner tutor instructions use the new goals, ordered capabilities, productive recall, and a default maximum of two new items. Shared displayed objective labels remain unchanged; adaptive saved focus/budget and structured recall selection belong to Part 2.

Timed wrap-up delivery is implemented through `SessionControlModel` and migration `0016_session_wrap_up_control.py`. Independent review found no blockers. **154 backend tests, full Ruff, full mypy across 76 files, and migration upgrade/downgrade/re-upgrade with clean Alembic metadata checks passed.** No live OpenAI provider call was performed. Automated lesson advancement and Decisions scoring remain unimplemented.

## Part 2: extractor, learnings, and lesson selection

### What we actually want to capture

Capture two streams: language learnings/progress and user insights about the person. Do not turn normal help during first exposure into a lasting weakness. A learner can practice successfully with support on the first day and need no continuing help later.

| Information | What to capture | Purpose |
| --- | --- | --- |
| New language introduced | Actual target-language word, phrase/frame, or conversation move, with an exact tutor teaching quote. | Make relevant material available for next-session practice. Introduction alone is exposure. |
| Language practiced | Actual learner use, exact quote, and preceding tutor context. | Know what to recall and verify how the learner used it. |
| Conversation skill practiced | The lesson capability the contribution serves, with grounded evidence and an observed performance level. | Track progress toward conversation, not only vocabulary acquisition. |
| Recurring need for help | Help with the same item/capability across later recall sessions, once a recurrence rule is met. | Choose a useful future practice target. Do not save a weakness from one introduction or one difficult attempt. |
| User insight | An optional short, precise, useful real fact, with exact source evidence and temporal context. Capture only after language learnings are covered. | Personalize a future conversation; do not attempt to record every fact or treat it as proficiency evidence. |

Keep recap summaries brief. Separate structured records can link multiple items to the exact evidence without expanding the recap into an assessment report. Three existing bundled observations are not a reliable representation of five individually reusable targets, so the new collections need their own bounds. Detect overruns instead of truncating them into apparent compliance.

### User insights: selective, precise, and lowest priority

Capture only volunteered real facts that are useful for a future conversation. **Language learnings and lesson progress come first; insights are optional and lowest priority.** Return none when the conversation offers no useful fact or when the learning work needs the available attention.

Use a small code-owned output bound, initially zero to two insights per session, with each insight one precise sentence up to 120 characters. Preserve the particular activity, role, place, or event that makes the fact useful, without adding an unsupported conclusion. Avoid generic personality labels and a running biography.

**Do not hardcode categories, example facts, or scenario lists into the extractor prompt.** The earlier location/interest/occupation/experience list was illustrative and is removed from the proposed runtime contract. Use a generic instruction to return a small number of useful, precise, explicitly volunteered facts after the language learnings. The output does not require a fixed category enum.

Use the same extraction request, with a separate `user_insights` collection. Each candidate contains concise factual text, exact learner quote/turn, source session, and optional temporal context. Code enforces the length/count limits and ownership. A dated experience remains a dated fact; doing something alone does not imply liking it. Resolve relative dates from the session timestamp and learner timezone only when supported, preserving uncertain dates rather than inventing precision.

Decisions verifies that a proposed insight is explicit, correctly represented, useful for conversational reuse, and offered as true of the learner. Role-play, imagined examples, copied model sentences, and requests to translate a hypothetical statement are not personal facts. Language practice and personal-fact extraction can use the same turn, but are evaluated separately.

Persist accepted facts in a **user-owned insight collection** with `user_id`, source references, temporal metadata, version, and deletion/suppression controls. Reuse relevant existing insights instead of repeatedly saving the same fact. Preserve separate dated events and supersede an ongoing fact when the learner explicitly corrects it. Do not overwrite learner edits with automatic capture.

The current `LearnerFileEntryModel` stores insights under a language profile and restricts its categories. Moving to the new user-owned, category-free collection requires a dedicated read/edit/delete path and migration of eligible existing insights through the profile's owning user. Preserve edits, deletion tombstones, expiry, and source references. Language-learning entries remain profile-owned.

### What a conversation-skill observation looks like

A capability is something the learner can do with another person. A practice observation is a concrete moment in which they tried it.

An illustrative lesson-1 exchange: the tutor asks what the learner enjoys, and the learner says **我喜欢排球**. That practices the capability **express a familiar detail**. The item **我喜欢** is reusable language; **排球** is vocabulary. The exact source turns establish what happened. A later relevant question or reaction can separately practice **return the turn**.

The result should identify the capability, the actual practiced language, and the source references. It should not store a vague claim such as “did an introduction” or assume the learner has mastered the capability. This example belongs in the review document only; it is not a dialogue to insert into tutor prompts.

### Why the question matters

The former “opportunity type” field meant **what kind of response the tutor's question invited**. Asking the learner to express a detail exercises production. Supplying the detail and asking for yes/no confirmation may demonstrate understanding, but does not show retrieval of the longer expression. Asking the learner to repeat a supplied answer practices the form with a model.

Use this distinction inside the scoring rubric and evidence review. It does not need to become a separate learner-facing learning or a durable taxonomy of every tutor question. Keep the actual question quote as provenance and score the relevant learner response in context.

Similarly, remove the proposed standalone “missing opportunity” record. When there is no assessable attempt for a capability, return no performance observation for it and leave its progress unchanged. This prevents an unasked question from becoming a failed skill. A failed attempt, an unclear attempt, and no attempt are different states.

### Assistance should mean a recurring need, not first-time learning

Do not create a durable learner-facing assistance learning after one call. The proposed recurring-help state should activate only when the same eligible item or capability needs help in **at least two distinct later recall sessions**, excluding its first introduction. This is an initial rule to evaluate, not a permanent weakness diagnosis.

For example, help while first learning a phrase is normal. Help again in one later recall session remains a single recall difficulty. Help across two later recall sessions can justify prioritizing that phrase for additional practice. Later successful independent recall clears or reduces the current need according to the versioned rule.

A judge must still inspect whether an answer was supplied in the current attempt: otherwise a copied answer could be credited as independent performance. Preserve that distinction in the grounded performance evaluation. It should not automatically become an ongoing learner trait, a recap criticism, or a lower overall level. Existing per-attempt assistance provenance can remain an audit fact; the new persistent **needs help** projection is created only from recurrence across sessions.

This is the distinction I recommend: factual context for judging one attempt versus a useful cross-session learning to act on. The tutor adjusts present support from the current response instead of being told that the learner always needs help.

### Use the Decisions API for review and a progress scale

**Selected approach: structured extraction followed by Decisions verification and a lesson-owned cumulative benchmark.** Use the latest transcript and the learner's accumulated language learnings. Code preserves the result and applies the configured progression policy; it does not replace the model's semantic judgment with a generic score/count rule.

The official API offers `predicate`, `choice`, and `score` questions. Its native name for an ordered scale is `score`; the supplied `levels` define the rubric. It returns probabilities and typed results, but does not generate arbitrary extracted fields or explanation text. Keep Responses Structured Outputs for the item/quote extraction. [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)

The input can be a serialized text representation of the latest transcript, pinned lesson criteria/rubric, accumulated eligible language learnings, and grounded current candidates. We can construct structured data in code and serialize it into that text, but it is not an unrestricted JSON-schema input/output endpoint. Give questions stable names that map to server-validated candidate IDs. Use independent verification and scoring questions in one request over shared evidence; code combines their answers after the response. [Decisions create reference](https://developers.openai.com/api/reference/python/resources/decisions/methods/create)

The current Python dependency is OpenAI 2.x. The official Decisions examples require Python SDK 3.26.0 or later; that SDK migration belongs to the proposed Part 2 integration, with adapter compatibility tests. The guide currently identifies `gpt-6-luna` as the supported Decisions model. [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)

### Success criteria and benchmark belong to each lesson

**Each lesson defines what success means and the ordered scale used to benchmark it.** Package the goal, capabilities, success criteria, and benchmark-level descriptions together under one immutable lesson-content version. The extractor and Decisions adapter receive that version's data; neither contains a second hardcoded definition of lesson success.

Extend the Part 1 lesson contract in Part 2 with:

- `success_criteria`: observable conversational outcomes, including what counts as independent use and retained language for this lesson.
- `benchmark_levels`: ordered descriptions of progress toward those outcomes.
- `benchmark_version`: the published identity for that rubric and its interpretation.

The Decisions `score` question is compiled from the selected lesson's criteria and levels. It benchmarks **the latest finalized transcript plus all accumulated eligible language learnings for the same profile**, using the source-session dates and evidence. User insights and editable personal summaries do not establish success.

This replaces the earlier universal per-attempt scale. The following is an initial lesson-specific rubric draft for discussion, not hardcoded extractor instructions:

| Level | Lesson 1: first two-way conversation | Lesson 2: keep a familiar conversation going |
| --- | --- | --- |
| 0. Beginning | There is assessable practice, but the evidence does not yet show a meaningful two-way exchange. | There is assessable practice, but contributions do not yet develop a connected thread. |
| 1. Building with support | The learner shares/responds and returns the turn with useful support. | The learner connects details or handles a follow-up with useful support. |
| 2. Achieving the goal | The learner independently shares a familiar detail, answers a related question, and contributes a reciprocal move. | The learner independently connects relevant details, handles a follow-up, and contributes to the thread. |
| 3. Retaining and extending | The accumulated evidence shows the exchange repertoire recalled in later sessions and reused in fresh exchanges. | The accumulated evidence shows connected conversation retained across sessions and developed in fresh exchanges. |

No assessable evidence is **unobserved**, not level 0. A first supported encounter can be useful progress without generating a recurring-help claim. The model should use chronology: later difficulty can qualify an earlier success, while an unasked capability does not erase earlier evidence.

Record criterion-level results as well as the lesson benchmark so the next session can target the useful next step. A high global average must not conceal an unmet lesson criterion. Named questions can evaluate individual criteria and the whole lesson against the same cumulative input.

The API's score is a probability-weighted mean of level indices, so retain the distribution, rubric version, and input-history revision. Do not round a mean into a claimed achievement. Advancement uses a named experiment-policy configuration applied to the lesson's benchmark and required criteria. Thresholds remain open as we experiment through the cycle. [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)

### What “all past learnings” means in the benchmark

Use the complete eligible accumulated language-learning record for the owned profile, including relevant earlier lessons. Do not substitute the last three memory entries or only the prior benchmark score. Represent repeated practice compactly as reusable items, dated occurrences, outcomes, and exact source references while preserving all contributing evidence.

The latest transcript supplies the current exchange; earlier raw transcripts do not need to be resent in full when their accepted learnings already preserve the relevant evidence. Retrieve prior source excerpts when the rubric needs surrounding context that the accepted record does not contain. Record the history revision and coverage used in each benchmark so a result can be audited.

If the complete learning history exceeds the model-input budget, process it by criterion in evidence-preserving batches and compose a complete criterion history before the final benchmark. Do not silently keep only the newest entries. An incomplete or refused benchmark cannot be treated as proof of readiness. This is a scalability path; the initial two-lesson experiment can normally supply its complete history directly.

Rebuilding the records and recall facts from accepted events remains deterministic. **Re-evaluating semantic lesson progress against a different history or rubric requires a Decisions benchmark**, not merely adding old numeric scores. Historical results remain pinned to their source data and rubric version.

### The pipeline and responsibility boundaries

| Stage | Input | Output / owner |
| --- | --- | --- |
| 1. Extract | Latest finalized transcript, pinned lesson definition, and known language items; relevant owned context only as needed. | Responses Structured Outputs prioritizes reusable language, exact quotes, and capability evidence, then optional useful user insights. |
| 2. Ground | Proposed items/attempts and current owned transcript. | Code validates schema, profile/lesson ownership, known keys, quote spans, bounds, and references. |
| 3. Verify and benchmark | Latest transcript, pinned lesson success criteria/levels, complete accumulated eligible language learnings, and grounded current evidence. | Decisions verifies claims and benchmarks criteria/lesson progress against the cumulative evidence. User-insight verification is separate from the proficiency benchmark. |
| 4. Commit progress | Accepted evidence, dated learning history, Decisions benchmark/distributions, and configured policy. | Code derives recall/recurrence facts, preserves the benchmark, and computes eligibility under the experiment policy. Commit with evidence and recap. |
| 5. Select the next session | Committed snapshot, eligible recall items, and learner topic/word requests. | A deterministic planner called by SessionService saves the next lesson, focus, recalls, and new-item limit. |

The normal benchmark uses the latest transcript plus complete accumulated learnings. Known item IDs avoid treating recall as new teaching. Current candidates remain untrusted and are checked against literal source context; a benchmark cannot gain eligibility from rejected evidence. Verification and benchmark questions are independently defined over their supplied source data and can be batched, with code combining results. A dependent follow-up evaluation uses another request rather than assuming an earlier answer.

Introduce a Decisions review adapter with a contract for named verification and score results. Use it for the new lesson-cycle experiment from the start; a comparison against the old reviewer is not a prerequisite. Preserve old result formats and historical records for compatibility. Decisions does not return the current reviewer's freeform reason field: store the typed result, question/rubric version, and exact source references, with any learner explanation rendered from known labels in code. Do not invent a model-written reason.

### Durable records

| Record | Minimum content |
| --- | --- |
| User insight | User ID, short factual text, exact source quote/turn/session, optional temporal context, confirmation/edit version, and deletion/suppression state. No required category enum. |
| Learning item | Server ID, language profile, actual target-language form, meaning/function, kind, compatible capabilities, and eligibility/suppression state. |
| Introduction and practice links | Source analysis, item/capability, exact evidence references, reviewed practice outcome, and session identity. Reuse existing provenance. |
| Lesson benchmark | Profile/lesson, pinned success criteria/rubric, history revision/coverage, criterion and lesson distributions, exact source references, and experiment-policy interpretation. |
| Learning snapshot | Profile revision, active lesson, latest committed lesson benchmark, accumulated evidence, encounter count, recall history, and recurring-help projections. |
| Session learning plan | Source snapshot and policy/content versions, selected lesson/focus, ordered recall references/pinned data, and new-item allowance. |

Keep item identity and evidence distinct from editable learner-file summaries. Do not merge synonyms or different constructions through a loose text hash. Reviewed aliasing can associate variants. Profile and language ownership, deletion/suppression, and exact provenance continue to apply. Keep retrieval bounded through indexes by profile, item, and source session.

### Where progress and insights belong

**Yes, progress belongs to the learner, scoped to their language profile.** The files `curriculum/progress.py` and `curriculum/planning.py` contain reusable algorithms; they do not hold a global progress value. Stored snapshots and item histories are keyed by `language_profile_id`, whose `user_id` establishes ownership.

| Data | Owner | Can it be reused in another language profile? |
| --- | --- | --- |
| User insights | User account (`user_id`). | Yes, as relevant conversational context about the same person. |
| Practice items, capability evidence, recall history, and progress snapshots | Owned language profile (`language_profile_id`). | No automatic proficiency or recall transfer. |
| Lesson definitions and scoring rubrics | Published curriculum version. | Shared definitions, with no learner state inside them. |
| Session plan and extracted evidence | Owned session, linked to its profile/user. | Preserve the source context rather than reassigning evidence. |

A learner can discuss the same real interest while practicing Mandarin or French. Success with a Mandarin expression is not evidence that they can express it in French. SessionService reads the active profile's progress plus a bounded set of the user's eligible insights; insight facts influence conversation content, never pass criteria or new-language budgets.

Lock profile progress updates and user-insight updates under a consistent ownership/lock order. Deduplicate insight writes across sessions without merging different dated experiences. Suppression/editing at user scope must be honored in every language profile. Expose user insights through a user-owned read/edit/delete path; learner-file learnings remain scoped to their profile.

### Progression and how SessionService selects the lesson

Lesson 1 still targets expressing a familiar detail, answering a related question, and returning the turn. Its own rubric defines how those outcomes combine with later recall and variation. Decisions benchmarks the cumulative evidence against those criteria; code applies the agreed experiment policy to its result. Session counts and numeric averages do not independently declare success. Exact advancement thresholds remain open for discussion.

First-exposure supported practice is useful progress toward that goal. It does not count as independent readiness and does not create a recurring-help state. Capture any qualifying capability observed in the current lesson, even when it is beyond the session's primary teaching focus. Lesson 2 similarly accumulates connected detail, follow-up response, and initiative. No fixed vocabulary count or four-session threshold grants completion.

After each finalized call, commit accepted evidence, item links, recap, and a benchmark tied to its history revision. Serialize snapshot updates at profile scope. Retries apply one analysis once, and reanalysis supersedes a session's earlier active contribution. A usable encounter contains accepted learner practice, so reconnects and duplicate jobs cannot inflate the count. If another accepted analysis changes the history while a benchmark is running, keep the result as historical and rerun the benchmark on the new revision before using it for advancement. Do not label a stale cumulative score as current.

At the next creation, [SessionService](../../apps/backend/src/mori/modules/sessions/application.py) reads the owned profile's committed snapshot and calls the pure planner. Select lesson 1 until its criteria qualify, then lesson 2. Within the selected lesson, choose a capability to develop and a bounded recall set, retaining relevant lesson-1 material for lesson 2. Recurring help may raise recall priority; one supported first encounter must not dominate future planning.

Save the chosen plan with the existing session plan. Creation retries and reconnects retain the same selection and allowance. Bootstrap uses the saved selection, rechecking deletion/suppression eligibility and recording redactions in the actual prompt manifest. Pending or failed analysis leaves the prior snapshot intact without inventing failure or advancement.

### Components for Part 2

| Component | Responsibility |
| --- | --- |
| `learning/extractor.py`, `learning/prompt.py`, `learning/evidence.py`, `learning/domain.py` | Extract grounded targets/attempts under the pinned lesson contract and integrate typed Decisions results. |
| New learning Decisions adapter | Compile named verification and benchmark questions from lesson-owned criteria/levels; validate responses and pin history/rubric versions. |
| `learning/models.py`, `learning/application.py` | Persist accepted evidence, user-owned insights, and profile-owned progress in the analysis commit; preserve editable projections. |
| New user-insight service/read path | Query, correct, delete, and suppress insights at user-account scope across language profiles. |
| New `curriculum/progress.py`, `curriculum/planning.py` | Derive recall/recurrence facts and interpret committed lesson benchmarks under the experiment policy; select the next session without model calls inside these pure functions. |
| `sessions/application.py`, `sessions/models.py` | Read owned profile progress and relevant user insights, then save the companion learning plan. |
| `sessions/prompt.py` | Render the saved plan without model-driven lesson selection or lasting weakness claims from one attempt. |
| `sessions/schemas.py`, generated API client | Expose useful goal/focus/practiced-language summaries when the UI needs them. |

Part 1's definitions provide the common curriculum contract. Part 2's extraction, scoring, reducer, planner, and compiler integration ship as a compatible package after the design is agreed. The Part 1 teaching improvement can be implemented now without enabling unapproved automated progression.

### Experiment through the lesson cycle with Decisions

Use current-session fixtures plus multi-session histories. Include supported first learning followed by comfortable recall, repeated help across later recalls, unasked capabilities, recognition-only responses, model copying, independent unsuccessful attempts, flexible use, uncertain Decisions distributions, refusals, duplicate/out-of-order jobs, reanalysis, deletion, and profile isolation.

Use Decisions as the selected provider from the start of the experiment. Record its distributions, rubric version, source evidence, and next-session behavior so we can inspect the full lesson cycle together. Tune each lesson's rubric, acceptance/readiness thresholds, and recurring-help rules as we observe first learning, later recall, and fresh conversational use. Do not make comparison with the previous reviewer a release prerequisite.

The exact thresholds remain open rather than being treated as approved constants. Capture progress scores and recurring patterns during the experiment; lesson advancement should use an explicit experiment-policy configuration or controlled lesson selection until a qualifying rule is agreed. Retain historical content/result versions. Editable prose memories do not become fabricated structured evidence.

Include useful and unnecessary personal facts, dated experiences, role-play/copying, corrections, and deletion across profiles. Verify that insight capture remains selective, precise, short, and lower priority than learning capture. Test cumulative benchmarks against complete history, missing older evidence, stale revisions, and a changed lesson rubric.

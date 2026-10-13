# Learning module and tutor feedback review

Reviewed October 12, 2026 against the current working tree, including the existing uncommitted capture implementation.

Scope after review feedback: implement structured learning evidence, retain the tutor adaptation, and explain the progression slice. Personal-memory validation is outside this change.

## Purpose and agent scope

The learning module turns a finalized conversation into a recap and bounded context for future tutoring. Its implemented responsibilities are post-session extraction, reference and shape validation, transactional persistence, and learner inspection, correction, and deletion. A captured learning describes language content practiced; an insight describes a volunteered activity or occupation.

The live Mori tutor owns conversation, explanations, cues, and retries within a pinned lesson. Curriculum owns lesson definitions and deterministic selection. The planned learning engine owns evidence-based passage, mastery, and level decisions. Captured free text can guide a conversation, but it is not sufficient input for those durable decisions.

The current feedback path is:

1. The supervisor finalizes transcript turns and enqueues an analysis run in the same transaction.
2. The extractor produces mode-specific candidates using the transcript, selected languages, and the pinned lesson's key, label, and full guidance.
3. Deterministic validation checks exact quoted spans, learner roles, preceding tutor opportunities, lesson references, and bounds. A separate semantic review checks each learning claim against the full transcript; unsupported and uncertain observations are omitted.
4. Analysis commits the recap, observations, corrections, and Learner File entries atomically. Processing an already successful run does not duplicate those records.
5. A later call loads up to three active learning entries and five unexpired insights from the same language profile into server-compiled instructions. Fluent calls receive insights only.

This is contextual adaptation within calls. It does not train model weights, automatically rewrite the tutor's policy, or implement lesson progression. Changes to shared tutor behavior should be separately evaluated and published under a new policy version.

Evidence: [capture orchestration](../../apps/backend/src/mori/modules/learning/application.py), [finalization and enqueue](../../apps/backend/src/mori/modules/sessions/supervisor.py), [call context selection](../../apps/backend/src/mori/modules/sessions/application.py), and the [approved learning PRD](../learning-system-prd.md).

## Review findings

### Implemented: Structured evidence and a separate semantic review

The original validator accepted an unrelated past-tense claim supported only by "Hello." It checked that a quote existed but discarded that quote after validation. The revised path retains exact Unicode spans and reviews what the words actually support.

Each observation now has a pinned curriculum item key and one to five evidence occurrences. Each occurrence preserves a learner turn ID, verbatim quote, and character start/end positions; an optional preceding tutor opportunity with its own verbatim quote and positions; and assistance classified as `independent`, `cued`, `modelled`, or `unknown`. A self-initiated contribution may have no tutor opportunity. Offsets count Unicode code points from zero, with an exclusive end. A repeated excerpt must be expanded until it identifies one exact span in its turn.

The separate reviewer receives the full finalized transcript, the pinned languages and lesson, and the structurally accepted claims. Only `supported` decisions enter observations and future learning entries; each retains the review reason. The reviewer must check meaning, target-language practice, lesson relevance, the opportunity, and support for the assistance label. Unsupported and uncertain decisions are dropped. Missing, duplicate, malformed, refused, or failed review results fail the analysis before its write transaction; the same run can retry without duplicate records. Empty observations and Fluent sessions require no evidence-review request.

Semantic review is another model judgment, not a proof of correctness or a mastery decision. It adds one provider request to learning analyses with usable candidate observations and still requires transcript evaluation. The current configured extractor model performs both calls with provider storage disabled.

Migration `20261012_0015` adds these fields and reference indexes. Existing observations remain `legacy`, with no invented spans, assistance, curriculum key, or review reason. Their existing prose can remain tentative conversation context; future progression must exclude legacy records. Learner edits continue to change a separate Learner File projection, preserving the underlying evidence.

Evidence: [provenance and review decisions](../../apps/backend/src/mori/modules/learning/evidence.py), [provider requests](../../apps/backend/src/mori/modules/learning/extractor.py), [atomic persistence](../../apps/backend/src/mori/modules/learning/application.py), and [migration](../../apps/backend/migrations/versions/0015_structured_learning_evidence.py).

### P2: The progression feedback loop remains unimplemented

The analysis commit writes recaps and capture records, but no lesson state, learning snapshot, due items, or level decisions. Session planning supplies profile mode, provisional level, topic, and requested words without prior learning state. The catalog's evidence rules are disabled. Session count and learning prose therefore cannot advance the learner through the course.

Recommendation: implement the planned versioned evidence rules and atomic state/snapshot commit, then wire those committed inputs into planning. Keep qualitative adaptation available while those rules are developed.

Evidence: [analysis commit](../../apps/backend/src/mori/modules/learning/application.py), [planning inputs](../../apps/backend/src/mori/modules/sessions/application.py#L231), and [disabled evidence rules](../../apps/backend/src/mori/modules/curriculum/catalog.py).

### P2: Retrieval and progression eligibility need further work

Retrieval selects by update time rather than curriculum relevance or a review schedule. Corrections appear in recaps but are not selected as explicit future repair targets. The new assistance labels and tutor opportunities make practice inspectable, but do not themselves establish success, distinct task variety, or sufficient evidence for passage.

Recommendation: evaluate extraction and semantic review for every supported language, define lesson-specific attempt outcomes and opportunity variety, then build curriculum-linked repair/review selection from committed evidence.

Evidence: [structured extraction](../../apps/backend/src/mori/modules/learning/extractor.py), [evidence records](../../apps/backend/src/mori/modules/learning/evidence.py), and [context selection](../../apps/backend/src/mori/modules/sessions/application.py).

## What the progression slice would look like

This is a proposed next slice. Passage, review scheduling, and level changes remain disabled.

### 1. Publish explicit lesson criteria

For each of the ten lessons and supported learning levels, define the conversational capability, what counts as a relevant opportunity, how varied independent attempts demonstrate it, and what yields `needs_practice` or `insufficient_evidence`. Publish the numerical thresholds and a version for the rule set. Lesson 10 also needs sufficient connected time for its seven-minute capability. Pronunciation and level decisions need their separate evidence policies. Completing a lesson must not silently switch someone into Fluent practice.

### 2. Evaluate attempts with pure rules

Use only structurally accepted, semantically supported records from the same profile and pinned curriculum. Require valid opportunity and assistance data. Keep assisted practice visible while counting only qualifying independent attempts toward passage. Define explicit outcomes for unsuccessful or unclear attempts, too; a missing capture must not be treated as a failed attempt. Deduplicate provider turns and overlapping claims so multiple descriptions of one answer cannot become multiple opportunities.

Return a lesson decision with exact supporting references and a bounded repair need. Insufficient evidence leaves prior progression unchanged. Lesson decisions and level assessment remain separate. Do not derive mastery from editable Learner File text or a confidence number alone.

### 3. Commit a complete state atomically

After provider work finishes, lock the profile through the same account-lock order used by session creation. Read the latest committed state, apply the pinned pure rules, and append the lesson/item decisions, recap, repair/review state, and a new planning snapshot in one transaction with successful run status. Use unique analysis-run/lesson/rule identities for idempotency. A snapshot points to its immutable decisions; a later plan sees either the previous complete snapshot or the new complete snapshot.

Retries do not increment progress twice. Delayed or failed analysis leaves the previous snapshot available. Out-of-order jobs must incorporate already committed evidence under the lock instead of replacing newer state with an older session's projection. Removing source evidence requires the approved derived-state rebuild.

### 4. Feed the committed snapshot into planning

The pure selector already accepts `mastered_keys`, `due_keys`, and `repair_keys`. Populate those from the committed snapshot. Its current shared-course priority is repair, then due review, then the first unfinished lesson. Introduce explicit due-time ordering and stable ties when scheduling is implemented. Freeze the selected lesson and snapshot reference in the session plan; reconnects keep that plan.

For future tutor context, select supported expressions relevant to the chosen lesson plus one due review or repair target, within the existing context bound. Personal topic preferences can shape the setting without contributing skill evidence.

### Concrete learner example

In lesson 1, the learner repeats a supplied introduction. Store the attempt as `modelled`; it is useful practice but not independent passage evidence. If there is no adequate independent evidence, retain lesson 1. The next call invites an introduction with a fresh personal detail before offering a phrase.

Later, independent introductions and connected responses meet the published lesson criteria. Commit a `demonstrated` decision and its supporting references, then a snapshot marking lesson 1 complete. The next plan selects lesson 2. If a later qualifying recall attempt shows a specific difficulty, commit a repair need and choose a suitable review encounter. The app can explain this as "You introduced yourself without a model. Next, we'll connect a few more details about your life." These are proposed behaviors, not evaluated thresholds or implemented progression.

### Remaining gates

Approve and publish passage thresholds, attempt-outcome and opportunity-variety criteria, and a review schedule. Evaluate the extractor/reviewer against a multilingual fixture corpus. Then verify atomic snapshots, concurrent and out-of-order analyses, retries, reconnects, stale state, and derived-state rebuilds. Measure the added semantic review request against the recap latency target before enabling it for learners.

## Experience changes implemented

New plans use `mori-framework-v4`. Compatible v2/v3 plans receive the corrected v4 policy on later call bootstrap, recorded in the call's manifest; saved lesson selection and historical call metadata remain unchanged.

- A returning learner with learning context gets a brief welcome and a new question that builds on recorded practice. The tutor waits for an answer before teaching, translating a phrase, or supplying a model response.
- The tutor chooses at most one relevant prior expression or conversation move and invites its use in a fresh situation before giving a model answer.
- Comfortable use leads to a connected detail. Hesitation leads to a small cue, followed by an explanation/model and retry if needed.
- Beginner assumes familiar greetings, name/origin introductions, and common short phrases regardless of captured context. Lesson 1 starts with daily-life detail beyond those basics, and does not ask the learner's name or restart a basic self-introduction. Requested or needed help with basics remains available.
- Entries are explicitly treated as potentially edited reports of practice. Current performance determines support; records do not imply mastery or level changes.
- Fluent practice receives personal insights without learning entries or the adaptive teaching section.
- Existing deletion and expiry filters continue to control context eligibility; ordering now includes an ID tie-breaker.

For example, after practicing 我喜欢 while discussing volleyball, a later suitable lesson can invite the learner to talk about another activity they enjoy. If they can reuse the expression, Mori extends the conversation. If they struggle, Mori offers a cue and helps them retry. This is an intended interaction example, not a measured live-call result.

Implementation: [prompt compiler](../../apps/backend/src/mori/modules/sessions/prompt.py) and [context selection](../../apps/backend/src/mori/modules/sessions/application.py).

## Correction after real-call feedback

The learner reported that v3 still asked their name. The two most recent local calls had v3 prompt-build manifests, three eligible learning entries including the edited introduction naming Jason, and opening transcripts that explicitly taught 我叫 and asked for the learner's name. The context reached call compilation; the lesson still instructed the tutor to invite a preferred name. A generic welcome-back instruction did not resolve that conflict.

The v4 correction aligns the published lesson guidance with the existing PRD's Beginner baseline, removes the name invitation, reuses supplied details, and requires the opening question before instruction. The earlier tests checked prompt assembly without evaluating the generated opening; new opt-in checks exercise the configured Realtime model directly.

The local development database was upgraded from `20261012_0014` to `20261012_0015`. Its two waiting analyses were processed successfully and both sessions became ready. The local `mori-dev-analysis` worker is running for future captures. This was a local runtime repair, with no production deployment.

## Verification and remaining evaluation

The complete backend suite passed 124 tests. Evidence checks cover exact Unicode spans, ambiguous excerpts, pinned lessons, tutor-role and sequence checks, semantic rejection/uncertainty, incomplete reviews, provider refusal, persistence gates, retry idempotency, edits preserving evidence, and the legacy migration. A call-bootstrap regression also verifies that an immutable v3 plan uses captured introduction context and records the resolved v4 policy. Model metadata matches the migrated schema. Ruff lint passed across source, tests, migrations, and the evaluator; Mypy passed across all 76 source files. The exported OpenAPI contract is unchanged.

Live evaluation against the configured `gpt-realtime-2.1` model passed six text scenarios (returning introduction, returning interest, and first Beginner, with two trials each) and two audio-output scenarios for the captured introduction. Each scenario includes an opening and one follow-up. None asked the learner's name, restarted 我叫, or began with the flagged phrase-teaching patterns. Responses were also reviewed directly. The provider's acknowledged instructions hash matched the compiler in each case. Reports are stored locally in `.codex/tutor-opening-evaluation.json` and `.codex/tutor-opening-audio-evaluation.json`; fixtures are synthetic and do not create application sessions or consume learner grants.

The evaluator uses [Realtime text and audio output](https://developers.openai.com/api/docs/guides/realtime-conversations). Its checks are targeted heuristics plus transcript review, not a guarantee across all conversations. Audio-output transcripts do not establish acoustic quality, microphone behavior, or browser delivery. A learner study and broader multilingual tutor and semantic-review evaluation remain outstanding. Evaluate requested help, unrelated topics, incorrect captured context, and Fluent isolation before judging broader experience quality.

Structured evidence and tutor adaptation are implemented. The next learning-system slice is published deterministic rules, atomic derived state, and snapshot-driven planning. Personal-memory validation is outside this review's selected scope.

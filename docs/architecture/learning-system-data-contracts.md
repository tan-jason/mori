# Learning system data contracts

**Status:** Approved design for implementation handoff

**Date:** September 26, 2026

This is the object structure for the learning-system records and public read models. Field names below use API-style camelCase; SQL columns use snake_case. `UUID` means a PostgreSQL UUID and `Instant` means `timestamptz`. Optional fields are marked `?`. Every owned record is scoped through its parent profile or session, and the application checks the authenticated user before reading or writing it.

## 1. Relationship map

```mermaid
erDiagram
    users ||--o{ language_profiles : owns
    language_profiles ||--|| learner_preferences : has
    language_profiles ||--|| profile_learning_settings : has
    language_profiles ||--o{ sessions : starts
    sessions ||--o| session_plans : pins
    session_plans ||--|{ session_plan_objectives : selects
    session_plans ||--o{ session_plan_memory_refs : references
    sessions ||--o{ session_call_attempts : connects
    session_call_attempts ||--o| session_prompt_builds : compiles
    session_call_attempts ||--o{ session_turns : records
    sessions ||--o{ analysis_runs : analyzes
    analysis_runs ||--o| recaps : produces
    analysis_runs ||--o{ learning_evidence : accepts
    language_profiles ||--o{ learner_item_states : derives
    language_profiles ||--o{ level_assessments : derives
    language_profiles ||--o{ learner_state_snapshots : snapshots
    language_profiles ||--o{ memories : remembers
    memories ||--o{ conversation_hooks : supports
    language_profiles ||--o{ memory_suppressions : suppresses
    course_catalog ||--o{ curriculum_versions : publishes
    curriculum_versions ||--o{ curriculum_items : contains
    curriculum_versions ||--o{ curriculum_edges : orders
    curriculum_versions ||--o{ evidence_rules : evaluates
```

Existing `users`, `language_profiles`, `learner_preferences`, `sessions`, `session_plans`, and `session_plan_objectives` are extended. The other records are new. A profile belongs to exactly one base/target pair; a session pins exactly one profile and course version. Profile changes never transfer evidence or memories to another pair.

## 2. Shared values and ownership

```ts
type UUID = string; // canonical UUID in API JSON
type Instant = string; // RFC 3339 timestamp in API JSON
type Level = "beginner" | "intermediate" | "advanced" | "fluent";
type StartingChoice = Level | "unsure";
type Mode = "learning" | "practice";
type AssessedLevel = "beginner" | "intermediate" | "advanced";
type ObjectiveKind = "graded" | "conversation_focus";
type AnalysisStatus = "pending" | "running" | "succeeded" | "failed";
type RecapStatus = "processing" | "ready" | "failed";
type SessionState = "created" | "reserved" | "planned" | "connecting" | "active"
  | "reconnecting" | "ending" | "analysis_pending" | "ready" | "analysis_failed"
  | "setup_failed";
```

`fluent` is a practice-mode choice, never an assessed `AssessedLevel`. First-session `unsure` starts provisional Beginner learning mode. `version` integers are optimistic-concurrency tokens; policy and curriculum version strings name immutable published artifacts. Content and model output are bounded and schema validated before persistence. A source turn ID is a stable server-owned turn ID, not a provider event ID supplied by the model.

The existing `users` table adds `version: number` for account-level `If-Match` when selecting the active profile. It advances when onboarding completion or active-profile selection changes. `onboardingCompletedAt` stays nullable until an explicitly confirmed pair and starting mode exist.

## 3. Profile and published course

```ts
type LanguageProfile = { // existing table: language_profiles
  id: UUID; userId: UUID; baseLanguageId: string; targetLanguageId: string;
  status: "active" | "archived"; languageSelectionConfirmedAt?: Instant;
  version: number; createdAt: Instant;
};

type LearnerPreferences = { // existing table: learner_preferences
  languageProfileId: UUID; correctionPreference: "light" | "balanced" | "frequent";
  tutorPace: "level" | "gentle" | "steady" | "natural";
  captionsEnabled: boolean; timezone: string; interests: string[];
  version: number; updatedAt: Instant;
};

type ProfileLearningSettings = { // new table: profile_learning_settings
  languageProfileId: UUID; startingChoice: StartingChoice;
  provisionalLevel?: AssessedLevel; mode: Mode;
  version: number; createdAt: Instant; updatedAt: Instant;
};

type CourseCatalog = { // new table: course_catalog
  id: UUID; baseLanguageId: string; targetLanguageId: string;
  status: "draft" | "published" | "retired";
  activeCurriculumVersionId?: UUID; pairPolicyVersion?: string;
  voicePolicyVersion?: string; publishedAt?: Instant;
};

type CurriculumVersion = { // new table: curriculum_versions
  id: UUID; courseCatalogId: UUID; version: string;
  status: "draft" | "published" | "retired"; publishedAt?: Instant;
  contentDigest: string;
};

type CurriculumItem = { // new table: curriculum_items
  id: UUID; curriculumVersionId: UUID; itemKey: string;
  kind: "vocabulary" | "grammar" | "conversation" | "pronunciation";
  level: AssessedLevel; learnerLabel: string; targetLanguageContent: string;
  selectionWeight: number; enabled: boolean;
};

type CurriculumEdge = { // new table: curriculum_edges
  curriculumVersionId: UUID; prerequisiteItemId: UUID; dependentItemId: UUID;
  kind: "requires";
};

type EvidenceRule = { // new table: evidence_rules
  id: UUID; curriculumVersionId: UUID; itemId: UUID;
  ruleVersion: string; evidenceKind: "use" | "comprehension" | "repair";
  minimumDistinctTurns: number; confidenceThreshold: number;
  masteryThreshold: number; enabled: boolean;
};
```

`users.onboardingCompletedAt` is nullable until an owned profile has an explicitly confirmed published pair and starting mode. The existing unique `(userId, baseLanguageId, targetLanguageId)` and one-active-profile partial unique index remain. `language_profiles.version` and `profile_learning_settings.version` advance on their own edits. Interests are normalized, deduplicated, length limited, and never treated as learning evidence. A catalog pair is selectable only when its active curriculum and pair/voice policies are published. Curriculum item keys are unique within a version, edges cannot cross versions or form cycles, and published course records are immutable. Pronunciation items may be presented live, but their evidence rules remain disabled for progression until an approved audio evaluator exists.

## 4. Session setup and Realtime records

```ts
type Session = { // existing table: sessions
  id: UUID; userId: UUID; languageProfileId: UUID;
  creationKeyDigest: string; setupRequestDigest: string;
  state: SessionState; rowVersion: number; connectedLimitMs: number;
  connectedMs: number; sessionExpiresAt?: Instant;
  endReason?: string; finalTurnSequence?: number;
  createdAt: Instant; updatedAt: Instant;
};

type SessionPlan = { // existing table: session_plans
  sessionId: UUID; schemaVersion: "learning_plan_v1"; mode: Mode;
  sourceSnapshotId?: UUID;
  profileVersion: number; preferenceVersion: number; settingsVersion: number;
  curriculumVersionId: UUID; selectionRuleVersion: string;
  basePolicyVersion: string; pairPolicyVersion: string; levelBlockVersion: string;
  selectedLevel?: AssessedLevel; topic?: string; requestedWords: string[];
  setupRequestDigest: string; objectiveCount: 1 | 2 | 3; createdAt: Instant;
};

type PlanObjective = { // existing table: session_plan_objectives
  sessionId: UUID; ordinal: 1 | 2 | 3; kind: ObjectiveKind;
  curriculumItemId?: UUID; learnerLabel: string;
};

type SessionPlanMemoryRef = { // new table: session_plan_memory_refs
  sessionId: UUID; memoryId: UUID; selectedAt: Instant;
};

type CallAttempt = { // new table: session_call_attempts
  id: UUID; sessionId: UUID; attemptNumber: number;
  providerCallId?: string; status: "creating" | "active" | "ended" | "failed";
  startedAt: Instant; endedAt?: Instant;
};

type PromptBuild = { // new table: session_prompt_builds
  callAttemptId: UUID; sessionId: UUID;
  basePolicyVersion: string; pairPolicyVersion: string; levelBlockVersion: string;
  modelAlias: string; voiceConfigVersion: string;
  selectedMemoryIds: UUID[]; instructionsSha256: string; createdAt: Instant;
};

type SessionTurn = { // new table: session_turns
  id: UUID; sessionId: UUID; callAttemptId: UUID; sequence: number;
  speaker: "learner" | "tutor"; finalText: string;
  providerEventId: string; startedAt?: Instant; endedAt?: Instant;
  quality: "usable" | "unclear" | "partial";
};
```

`SessionState` remains the existing database state union. `setupRequestDigest` binds idempotency to topic, requested words, and profile ID. A plan is written once for a session and is never silently edited after creation. A graded objective requires a same-version curriculum item; a conversation focus has no item. A memory reference is eligibility only, never a copy of text. The prompt build is one per call attempt; its selected IDs are an audit manifest, while the compiler filters currently revoked or expired memories before every provider bootstrap. Reconnect creates a new call attempt and prompt build under the same plan. `session_turns` is unique by `(sessionId, sequence)` and by `(callAttemptId, providerEventId)` to deduplicate provider replay. Only finalized turns at or below `finalTurnSequence` enter analysis. Do not store raw instructions, audio, or memory text in general logs.

The `SessionPlan` type above applies to new plans. Existing placeholder rows receive `schemaVersion: "legacy_placeholder"` and retain the original string `curriculum_version`, `selection_rule_version`, and `prompt_version` columns. A migration adds new nullable columns without changing historical rows; the application requires new-plan fields when `schemaVersion` is `learning_plan_v1` and reads legacy rows through a compatibility adapter. The existing objective `text` column remains the source for `learnerLabel` until a versioned migration renames it.

## 5. Analysis, derived learning state, and recap

```ts
type AnalysisRun = { // new table: analysis_runs
  id: UUID; sessionId: UUID; analysisPolicyVersion: string;
  extractionSchemaVersion: string; extractionModelAlias: string;
  curriculumVersionId: UUID; evidenceRuleVersion: string;
  mode: Mode; finalTurnSequence: number; status: AnalysisStatus;
  startedAt?: Instant; completedAt?: Instant; failureCode?: string;
};

type LearningEvidence = { // new table: learning_evidence
  id: UUID; analysisRunId: UUID; sessionId: UUID; languageProfileId: UUID;
  curriculumItemId: UUID; kind: "use" | "comprehension" | "repair";
  sourceTurnIds: UUID[]; confidence: number; acceptedAt: Instant;
};

type LearnerItemState = { // new table: learner_item_states, append-only decisions
  id: UUID; languageProfileId: UUID; curriculumItemId: UUID;
  sourceAnalysisRunId: UUID; state: "new" | "practicing" | "review_due" | "mastered";
  evidenceCount: number; nextReviewAt?: Instant; decidedAt: Instant;
};

type LevelAssessment = { // new table: level_assessments, append-only decisions
  id: UUID; languageProfileId: UUID; sourceAnalysisRunId: UUID;
  assessedLevel: AssessedLevel; confidence: number;
  rationaleTurnIds: UUID[]; ruleVersion: string; decidedAt: Instant;
};

type LearnerStateSnapshot = { // new table: learner_state_snapshots
  id: UUID; languageProfileId: UUID; sourceAnalysisRunId: UUID;
  curriculumVersionId: UUID; selectorStateSchemaVersion: string;
  assessedLevel?: AssessedLevel; levelConfidence?: number;
  itemStateIds: UUID[]; dueItemIds: UUID[]; repairItemIds: UUID[];
  createdAt: Instant;
};

type Recap = { // new table: recaps
  id: UUID; sessionId: UUID; analysisRunId: UUID; mode: Mode;
  status: RecapStatus; summary: string;
  learningDetails?: { schemaVersion: string; objectiveOutcomes: ObjectiveOutcome[];
    corrections: CorrectionExample[]; nextFocus?: string; levelChangeReason?: string };
  permittedMemoryIds: UUID[]; createdAt: Instant;
};

type ObjectiveOutcome = { objectiveOrdinal: number; result: "practiced" | "supported" | "needs_retry"; sourceTurnIds: UUID[] };
type CorrectionExample = { learnerTurnId: UUID; conciseSuggestion: string };
```

The worker treats extraction as candidate data. It validates exact turn IDs, ownership, curriculum version, confidence, consent, and deletion state before writing evidence. `LearningEvidence`, item decisions, level assessments, and snapshots exist only for learning mode; a short or unusable session yields no progress. Each successful run commits its derived rows, recap, permitted memories, and status in one transaction. `analysis_runs` has a unique `(sessionId, analysisPolicyVersion)` execution identity; retries reuse it, while an intentional new policy version creates a new auditable run. The current recap is the latest successful run's recap, never an untracked overwrite. A snapshot's IDs refer to immutable decision records, and a next plan reads only the latest committed snapshot. A practice recap has `learningDetails` absent by schema, not an empty object. Transcript-only correction evidence never increments pronunciation mastery.

The conceptual `sourceTurnIds`, `rationaleTurnIds`, and `itemStateIds` arrays above are assembled from normalized reference tables, not unchecked SQL arrays. `learning_evidence_turn_refs(evidence_id, turn_id)`, `level_assessment_turn_refs(assessment_id, turn_id)`, and `snapshot_item_state_refs(snapshot_id, item_state_id)` have composite primary keys and foreign keys to both sides. Their write transaction checks that all referenced records belong to the same profile and allowed finalized session or curriculum version. A snapshot's due/repair ID lists are bounded, versioned selector context assembled from its item-state references. This keeps exact-turn provenance and deletion behavior enforceable.

## 6. Personal context and deletion records

```ts
type Memory = { // new table: memories
  id: UUID; languageProfileId: UUID; sourceSessionId: UUID;
  sourceTurnIds: UUID[]; canonicalFactDigest: string;
  factText?: string; kind: "interest" | "preference" | "context" | "event";
  confidence: number; sensitivity: "low";
  observedAt: Instant; expiresAt?: Instant; revokedAt?: Instant;
  createdByAnalysisRunId: UUID;
};

type ConversationHook = { // new table: conversation_hooks
  id: UUID; languageProfileId: UUID; memoryId: UUID;
  questionHint: string; validUntil?: Instant; createdAt: Instant;
};

type MemorySuppression = { // new table: memory_suppressions
  id: UUID; languageProfileId: UUID; canonicalFactDigest: string;
  sourceMemoryId?: UUID; revokedAt: Instant; reason: "learner_deleted" | "session_deleted";
};
```

Only explicitly volunteered, low-sensitivity facts can become memories. The application normalizes a fact and computes `canonicalFactDigest` server-side; unique `(languageProfileId, canonicalFactDigest)` active-memory and suppression checks prevent retry or newer-version analysis from recreating deleted content. A hook refers to an active memory and expires with it. The selector and prompt compiler check current revocation and expiry, even if a plan still holds the ID. Deleting a source session revokes its memories and evidence, then rebuilds the affected profile's derived state from surviving evidence. A learner's future explicit save could override a suppression only through a separate, deliberate command, not through automatic extraction.

`memory_source_turn_refs(memory_id, turn_id)` supplies the `sourceTurnIds` in `Memory` with composite key and foreign keys. A transaction checks all source turns are learner turns from `sourceSessionId`. Revocation clears `factText`, retires the hook, and keeps only a digest-based suppression tombstone needed to prevent replay. The memory row may then be hard deleted. `MemorySuppression.sourceMemoryId` is nullable with `ON DELETE SET NULL`, so deleting a source memory or session cannot remove the suppression marker. The retention policy governs deletion of other session artifacts.

## 7. Public API read models

These are projections, not extra tables. OpenAPI is the source of truth for the generated web client. API responses use camelCase and never return raw prompt instructions, private memory context selected for a call, policy internals, or unvalidated model candidates.

```ts
type MeView = {
  user: { id: UUID; email: string; displayName: string; status: string };
  version: number;
  onboarding: { complete: boolean };
  activeLanguageProfile: LanguageProfileView | null;
  preferences: PreferencesView | null;
  csrfToken: string;
};
type LanguageProfileView = {
  id: UUID; baseLanguageId: string; targetLanguageId: string;
  status: "active" | "archived"; languageSelectionConfirmed: boolean;
  version: number;
  learning: { mode: Mode; startingChoice: StartingChoice;
    provisionalLevel?: AssessedLevel; assessedLevel?: AssessedLevel;
    version: number };
};
type PreferencesView = {
  correctionPreference: LearnerPreferences["correctionPreference"];
  tutorPace: LearnerPreferences["tutorPace"]; captionsEnabled: boolean;
  timezone: string; interests: string[]; version: number;
};
type SessionPlanPreview = {
  sessionId: UUID; mode: Mode; topic?: string;
  objectives: { ordinal: number; label: string }[];
};
type SessionRecapView =
  | { mode: "learning"; status: RecapStatus; summary?: string;
      objectiveOutcomes?: ObjectiveOutcome[]; corrections?: CorrectionExample[];
      nextFocus?: string; levelChangeReason?: string; memoryIds?: UUID[] }
  | { mode: "practice"; status: RecapStatus; summary?: string; memoryIds?: UUID[] };
type MemoryView = { id: UUID; factText: string; kind: Memory["kind"];
  observedAt: Instant; expiresAt?: Instant };
```

`POST /api/v1/language-profiles` takes the required explicit pair and `StartingChoice` plus optional preferences and interests. `PUT /api/v1/me/active-language-profile`, profile-scoped preference and learning-setting mutations, session setup, recap, and memory list/delete use the routes in the [implementation design](learning-system-implementation.md#4-public-api-contract). A pending or failed recap has no ready-only fields. ETags correspond to the owning `version` field and stale writes fail with `412`.

## 8. Field limits for the first published course

| Field | Limit and validation |
| --- | --- |
| `interests` | At most 12 entries, each 1 to 80 Unicode characters after trim and normalization; deduplicate case-insensitively. |
| Session `topic` | Optional, 1 to 160 Unicode characters when present. |
| Session `requestedWords` | At most 8 entries, each 1 to 60 Unicode characters; deduplicate after normalization. |
| Selected memory context | At most 5 active, unexpired facts for one prompt build; each `factText` is at most 240 Unicode characters. |
| `ConversationHook.questionHint` | At most 160 Unicode characters; never embeds a sensitive fact. |
| Evidence turn references | At most 5 finalized learner turns per item claim and 20 for a level assessment, all from the same session and curriculum context. |
| Confidence fields | Finite decimal value from 0 through 1, inclusive. Invalid or absent confidence fails candidate validation rather than defaulting to certainty. |

These limits apply in Pydantic and domain validation, with database checks where scalar length or numeric range can be enforced. No user-provided topic, word, interest, or memory becomes an instruction: the compiler labels it as untrusted context and escapes or rejects content that violates the prompt contract. Retention periods and numerical promotion thresholds remain the release decisions listed in the [implementation design](learning-system-implementation.md#10-decisions-still-required-before-release).

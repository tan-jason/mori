export type LearningLevel =
  | "Beginner"
  | "Intermediate"
  | "Advanced"
  | "Fluent";

export type LearningState =
  | "introduced"
  | "practiced"
  | "demonstrated"
  | "retained";

export interface SessionEntitlement {
  label: string;
  sessionsRemaining: number;
  sessionsIncluded: number;
  resetLabel?: string;
}

export interface LearningTerm {
  targetText: string;
  pronunciation?: string;
  meaning: string;
}

export interface LearningItem extends LearningTerm {
  id: string;
  state: LearningState;
}

export interface SessionHistoryItem {
  id: string;
  title: string;
  completedAtLabel: string;
  durationMinutes: number;
  status: "processing" | "ready";
}

export interface DashboardSnapshot {
  learner: {
    displayName: string;
    level: LearningLevel;
    levelDescription: string;
  };
  entitlement: SessionEntitlement;
  suggestedFocus: {
    eyebrow: string;
    title: string;
    description: string;
  };
  lessonPreview: {
    label: string;
    terms: LearningTerm[];
    prompt: string;
  };
  dueReviewCount: number;
  recentItems: LearningItem[];
  recentSessions: SessionHistoryItem[];
}

export interface RecapCorrection {
  before: string;
  after: string;
  explanation: string;
}

export interface SessionRecap {
  id: string;
  mode: "learning" | "practice";
  status: "processing" | "ready" | "failed";
  summary?: string;
  observations?: Array<{
    kind: string;
    detail: string;
    learnerTurnIds: string[];
  }>;
  corrections?: Array<{
    learnerTurnId: string;
    before: string;
    suggestion: string;
  }>;
}

export interface LearnerFileEntry {
  id: string;
  kind: "learning" | "insight";
  text: string;
  origin: "capture" | "learner_edit";
  version: number;
  sourceSessionId: string | null;
  createdAt: string;
  updatedAt: string;
  expiresAt: string | null;
}

export interface LearnerFilePage {
  entries: LearnerFileEntry[];
  nextCursor: string | null;
}

export type LearningLevel =
  | "Beginner"
  | "Learning Beginner"
  | "Intermediate"
  | "Conversational"
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

export interface LearningItem {
  id: string;
  hanzi: string;
  pinyin: string;
  meaning: string;
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
  title: string;
  completedAtLabel: string;
  durationMinutes: number;
  summary: string;
  objectives: Array<{
    label: string;
    outcome: "attempted" | "demonstrated";
  }>;
  corrections: RecapCorrection[];
  nextFocus: string;
}

export interface LearnerMemory {
  id: string;
  label: string;
  detail: string;
  sourceLabel: string;
  expiresLabel: string;
}

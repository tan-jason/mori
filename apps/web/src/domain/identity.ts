import type { LanguageProfile } from "./languages";

export type UserStatus = "active" | "suspended" | "deletion_pending";
export type LanguageProfileStatus = "active" | "archived";
export type CorrectionPreference = "light" | "balanced" | "frequent";
export type TutorPace = "level" | "gentle" | "steady" | "natural";
export type StartingChoice = "beginner" | "intermediate" | "advanced" | "fluent" | "unsure";
export type LearningMode = "learning" | "practice";

export interface LanguagePair {
  baseLanguageId: string;
  targetLanguageId: string;
  baseLanguageName: string;
  targetLanguageName: string;
  targetNativeName: string;
  available: boolean;
}

export interface LearnerPreferences {
  correctionPreference: CorrectionPreference;
  tutorPace: TutorPace;
  captionsEnabled: boolean;
  timezone: string;
  interests: string[];
  learningGoal: string;
  speakingContext: string;
  learningNotes: string;
  version: number;
}

export interface CurrentLearner {
  user: {
    id: string;
    email: string;
    displayName: string;
    status: UserStatus;
  };
  onboarding: {
    complete: boolean;
  };
  version: number;
  activeLanguageProfile: (LanguageProfile & {
    status: LanguageProfileStatus;
    languageSelectionConfirmed: boolean;
    version: number;
    learning: {
      mode: LearningMode;
      startingChoice: StartingChoice;
      provisionalLevel: StartingChoice | null;
      version: number;
    };
  }) | null;
  preferences: LearnerPreferences | null;
  csrfToken: string;
}

export type ReadyLearner = CurrentLearner & {
  activeLanguageProfile: NonNullable<CurrentLearner["activeLanguageProfile"]>;
  preferences: LearnerPreferences;
};

export function isReadyLearner(learner: CurrentLearner): learner is ReadyLearner {
  return learner.onboarding.complete &&
    learner.activeLanguageProfile?.languageSelectionConfirmed === true &&
    learner.preferences !== null;
}

export interface CreateProfileCommand {
  baseLanguageId: string;
  targetLanguageId: string;
  startingChoice: StartingChoice;
  correctionPreference: CorrectionPreference;
  tutorPace: TutorPace;
  timezone: string;
  interests: string[];
  learningGoal: string;
  speakingContext: string;
  learningNotes: string;
  idempotencyKey: string;
  csrfToken: string;
}

export interface PreferenceChanges {
  correctionPreference: CorrectionPreference;
  tutorPace: TutorPace;
  timezone: string;
  learningGoal: string;
  speakingContext: string;
  learningNotes: string;
}

export interface UpdatePreferencesCommand {
  changes: PreferenceChanges;
  expectedVersion: number;
  csrfToken: string;
}

export function getInitials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);

  if (parts.length === 0) {
    return "M";
  }

  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "";
  return `${first}${last}`.toLocaleUpperCase();
}

export function getFirstName(displayName: string): string {
  return displayName.trim().split(/\s+/)[0] || "Learner";
}

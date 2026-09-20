import type { LanguageProfile } from "./languages";

export type UserStatus = "active" | "suspended" | "deletion_pending";
export type LanguageProfileStatus = "active" | "archived";
export type CorrectionPreference = "light" | "balanced" | "frequent";
export type TutorPace = "level" | "gentle" | "steady" | "natural";

export interface LearnerPreferences {
  correctionPreference: CorrectionPreference;
  tutorPace: TutorPace;
  captionsEnabled: boolean;
  timezone: string;
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
  activeLanguageProfile: LanguageProfile & {
    status: LanguageProfileStatus;
  };
  preferences: LearnerPreferences;
  csrfToken: string;
}

export interface PreferenceChanges {
  correctionPreference: CorrectionPreference;
  tutorPace: TutorPace;
  timezone: string;
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

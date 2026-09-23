import type {
  DashboardSnapshot,
  LearnerMemory,
  SessionRecap,
} from "../domain/learning";
import type {
  CurrentLearner,
  UpdatePreferencesCommand,
} from "../domain/identity";

/**
 * Backend adapter boundary for the webapp.
 *
 * Keep transport details out of features. The backend integration can implement
 * this contract with REST, RPC, or generated clients once API contracts settle.
 */
export interface WebAppGateway {
  getCurrentLearner(signal?: AbortSignal): Promise<CurrentLearner>;
  updatePreferences(
    command: UpdatePreferencesCommand,
    signal?: AbortSignal,
  ): Promise<CurrentLearner>;
  logout(csrfToken: string, signal?: AbortSignal): Promise<void>;
  getDashboard(
    languageProfileId: string,
    signal?: AbortSignal,
  ): Promise<DashboardSnapshot>;
  getRecap(
    sessionId: string,
    languageProfileId: string,
    signal?: AbortSignal,
  ): Promise<SessionRecap>;
  getMemories(
    languageProfileId: string,
    signal?: AbortSignal,
  ): Promise<LearnerMemory[]>;
}

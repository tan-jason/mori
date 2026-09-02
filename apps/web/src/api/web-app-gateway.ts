import type {
  DashboardSnapshot,
  LearnerMemory,
  SessionRecap,
} from "../domain/learning";

/**
 * Backend adapter boundary for the webapp.
 *
 * Keep transport details out of features. The backend integration can implement
 * this contract with REST, RPC, or generated clients once API contracts settle.
 */
export interface WebAppGateway {
  getDashboard(signal?: AbortSignal): Promise<DashboardSnapshot>;
  getRecap(sessionId: string, signal?: AbortSignal): Promise<SessionRecap>;
  getMemories(signal?: AbortSignal): Promise<LearnerMemory[]>;
}

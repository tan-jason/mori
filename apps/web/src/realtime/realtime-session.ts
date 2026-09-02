export type RealtimeSessionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "ending"
  | "ended"
  | "failed";

export interface RealtimeSession {
  readonly state: RealtimeSessionState;
  connect(): Promise<void>;
  end(reason: "learner_ended" | "time_limit" | "connection_failed"): Promise<void>;
  setPlaybackRate(rate: number): Promise<void>;
}

export interface RealtimeSessionFactory {
  create(sessionId: string): RealtimeSession;
}

/**
 * The live implementation belongs behind this port. It will exchange a
 * short-lived credential or SDP through the application backend. A standard
 * provider API key must never be placed in the browser bundle.
 */
export const unconfiguredRealtimeSessionFactory: RealtimeSessionFactory = {
  create() {
    throw new Error("Realtime sessions are not configured in this scaffold.");
  },
};

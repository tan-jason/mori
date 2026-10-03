export type RealtimeSessionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "ending"
  | "ended"
  | "failed";

export interface TranscriptTurn {
  itemId: string;
  role: "learner" | "tutor";
  text: string;
}

export interface RealtimeSession {
  readonly state: RealtimeSessionState;
  readonly deadlineAt: string | null;
  connect(): Promise<void>;
  end(reason: "learner_ended" | "time_limit" | "connection_failed"): Promise<void>;
  setMicrophoneMuted(muted: boolean): void;
  setPlaybackRate(rate: number): Promise<void>;
  subscribe(listener: (state: RealtimeSessionState) => void): () => void;
  subscribeTranscript(listener: (turns: readonly TranscriptTurn[]) => void): () => void;
}

export interface RealtimeSessionFactory {
  readonly available: boolean;
  create(sessionId: string, csrfToken: string): RealtimeSession;
}

/**
 * The live implementation belongs behind this port. It will exchange a
 * short-lived credential or SDP through the application backend. A standard
 * provider API key must never be placed in the browser bundle.
 */
export const unconfiguredRealtimeSessionFactory: RealtimeSessionFactory = {
  available: false,
  create() {
    throw new Error("Voice practice is not available yet.");
  },
};

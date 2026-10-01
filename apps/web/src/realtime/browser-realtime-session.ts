import type {
  RealtimeSession,
  RealtimeSessionFactory,
  RealtimeSessionState,
} from "./realtime-session";

export interface SdpExchange {
  (sessionId: string, csrfToken: string, offerSdp: string): Promise<{
    answerSdp: string;
    attemptId: string;
    deadlineAt: string;
  }>;
}

export interface BrowserRealtimeTransport {
  exchangeSdp: SdpExchange;
  acknowledge(sessionId: string, attemptId: string, csrfToken: string): Promise<void>;
  requestEnd(sessionId: string, csrfToken: string): Promise<void>;
}

interface BrowserDependencies {
  peerConnection(): RTCPeerConnection;
  microphone(): Promise<MediaStream>;
  audio(): HTMLAudioElement;
}

const defaultBrowserDependencies: BrowserDependencies = {
  peerConnection: () => new RTCPeerConnection(),
  microphone: () => navigator.mediaDevices.getUserMedia({ audio: true }),
  audio: () => document.createElement("audio"),
};

function waitForIce(connection: RTCPeerConnection): Promise<void> {
  if (connection.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      connection.removeEventListener("icegatheringstatechange", check);
      reject(new Error("Your microphone connection timed out. Please try again."));
    }, 10_000);
    const check = () => {
      if (connection.iceGatheringState !== "complete") return;
      window.clearTimeout(timeout);
      connection.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    connection.addEventListener("icegatheringstatechange", check);
    check();
  });
}

function waitForChannel(channel: RTCDataChannel): Promise<void> {
  if (channel.readyState === "open") return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      channel.removeEventListener("open", open);
      channel.removeEventListener("close", closed);
      reject(new Error("The voice connection timed out. Please try again."));
    }, 15_000);
    const cleanup = () => {
      window.clearTimeout(timeout);
      channel.removeEventListener("open", open);
      channel.removeEventListener("close", closed);
    };
    const open = () => { cleanup(); resolve(); };
    const closed = () => { cleanup(); reject(new Error("The voice connection closed.")); };
    channel.addEventListener("open", open);
    channel.addEventListener("close", closed);
  });
}

class BrowserRealtimeSession implements RealtimeSession {
  state: RealtimeSessionState = "idle";
  private readonly listeners = new Set<(state: RealtimeSessionState) => void>();
  private connection: RTCPeerConnection | null = null;
  private microphoneStream: MediaStream | null = null;
  private audioElement: HTMLAudioElement | null = null;
  private attemptId: string | null = null;
  private cancelled = false;
  private deadlineTimer: number | null = null;
  private disconnectTimer: number | null = null;

  constructor(
    private readonly sessionId: string,
    private readonly csrfToken: string,
    private readonly transport: BrowserRealtimeTransport,
    private readonly browser: BrowserDependencies,
  ) {}

  subscribe(listener: (state: RealtimeSessionState) => void): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => { this.listeners.delete(listener); };
  }

  private setState(state: RealtimeSessionState): void {
    this.state = state;
    for (const listener of this.listeners) listener(state);
  }

  async connect(): Promise<void> {
    if (this.state !== "idle") throw new Error("The voice session has already started.");
    this.setState("connecting");
    try {
      this.microphoneStream = await this.browser.microphone();
      this.ensureOpen();
      const connection = this.browser.peerConnection();
      this.connection = connection;
      connection.onconnectionstatechange = () => {
        if (this.cancelled || this.state !== "connected" && this.state !== "reconnecting") return;
        if (connection.connectionState === "connected") {
          if (this.disconnectTimer !== null) window.clearTimeout(this.disconnectTimer);
          this.disconnectTimer = null;
          this.setState("connected");
        } else if (connection.connectionState === "disconnected") {
          this.setState("reconnecting");
          this.disconnectTimer ??= window.setTimeout(() => {
            void this.end("connection_failed").catch(() => {});
          }, 5000);
        } else if (connection.connectionState === "failed" || connection.connectionState === "closed") {
          void this.end("connection_failed").catch(() => {});
        }
      };
      const audio = this.browser.audio();
      audio.autoplay = true;
      audio.hidden = true;
      document.body.append(audio);
      this.audioElement = audio;
      connection.ontrack = (event) => {
        audio.srcObject = event.streams[0] ?? new MediaStream([event.track]);
      };
      for (const track of this.microphoneStream.getAudioTracks()) {
        track.enabled = false;
        connection.addTrack(track, this.microphoneStream);
      }
      const channel = connection.createDataChannel("oai-events");
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      await waitForIce(connection);
      this.ensureOpen();
      const offerSdp = connection.localDescription?.sdp;
      if (!offerSdp) throw new Error("Your microphone could not start. Please try again.");
      const answer = await this.transport.exchangeSdp(this.sessionId, this.csrfToken, offerSdp);
      this.attemptId = answer.attemptId;
      this.ensureOpen();
      await connection.setRemoteDescription({ type: "answer", sdp: answer.answerSdp });
      await waitForChannel(channel);
      this.ensureOpen();
      await this.transport.acknowledge(this.sessionId, answer.attemptId, this.csrfToken);
      this.ensureOpen();
      for (const track of this.microphoneStream.getAudioTracks()) track.enabled = true;
      this.setState("connected");
      this.deadlineTimer = window.setTimeout(() => {
        void this.end("time_limit").catch(() => {});
      }, Math.max(0, Date.parse(answer.deadlineAt) - Date.now()));
    } catch (error) {
      if (this.attemptId) {
        try {
          await this.transport.requestEnd(this.sessionId, this.csrfToken);
        } catch {
          // The server supervisor still owns cleanup and the session deadline.
        }
      }
      this.cleanup();
      if (!this.cancelled) this.setState("failed");
      throw error;
    }
  }

  async end(reason: "learner_ended" | "time_limit" | "connection_failed"): Promise<void> {
    void reason;
    if (this.state === "ended" || this.state === "ending") return;
    this.cancelled = true;
    this.setState("ending");
    let confirmed = false;
    try {
      if (this.attemptId) await this.transport.requestEnd(this.sessionId, this.csrfToken);
      confirmed = true;
    } finally {
      this.cleanup();
      this.setState(confirmed ? "ended" : "failed");
    }
  }

  setPlaybackRate(rate: number): Promise<void> {
    if (!Number.isFinite(rate) || rate < 0.5 || rate > 1.5) {
      return Promise.reject(new Error("Choose a playback speed between 0.5 and 1.5."));
    }
    if (this.audioElement) this.audioElement.playbackRate = rate;
    return Promise.resolve();
  }

  private cleanup(): void {
    if (this.deadlineTimer !== null) window.clearTimeout(this.deadlineTimer);
    this.deadlineTimer = null;
    if (this.disconnectTimer !== null) window.clearTimeout(this.disconnectTimer);
    this.disconnectTimer = null;
    this.connection?.close();
    this.connection = null;
    for (const track of this.microphoneStream?.getTracks() ?? []) track.stop();
    this.microphoneStream = null;
    if (this.audioElement) {
      this.audioElement.srcObject = null;
      this.audioElement.remove();
      this.audioElement = null;
    }
  }

  private ensureOpen(): void {
    if (this.cancelled) throw new Error("The voice connection was closed.");
  }
}

export function createBrowserRealtimeSessionFactory(
  transport: BrowserRealtimeTransport,
  browser: BrowserDependencies = defaultBrowserDependencies,
): RealtimeSessionFactory {
  return {
    available: true,
    create(sessionId, csrfToken) {
      return new BrowserRealtimeSession(sessionId, csrfToken, transport, browser);
    },
  };
}

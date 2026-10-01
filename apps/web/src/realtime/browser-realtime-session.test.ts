import { describe, expect, it, vi } from "vitest";
import { createBrowserRealtimeSessionFactory } from "./browser-realtime-session";

function browserHarness() {
  const stop = vi.fn();
  const close = vi.fn();
  const send = vi.fn();
  let onMessage: ((event: MessageEvent) => void) | null = null;
  const enabledWhenAdded: boolean[] = [];
  const track = { enabled: true, stop } as unknown as MediaStreamTrack;
  const stream = {
    getAudioTracks: () => [track],
    getTracks: () => [track],
  } as unknown as MediaStream;
  const connection = {
    iceGatheringState: "complete",
    connectionState: "connected",
    localDescription: { type: "offer", sdp: "v=0\r\noffer" },
    addTrack: vi.fn((addedTrack: MediaStreamTrack) => { enabledWhenAdded.push(addedTrack.enabled); }),
    createDataChannel: () => ({
      readyState: "open", send,
      addEventListener: (type: string, listener: (event: MessageEvent) => void) => {
        if (type === "message") onMessage = listener;
      },
    }),
    createOffer: () => Promise.resolve({ type: "offer", sdp: "v=0\r\noffer" }),
    setLocalDescription: vi.fn(async () => {}),
    setRemoteDescription: vi.fn(async () => {}),
    close,
  } as unknown as RTCPeerConnection;
  return {
    stop,
    close,
    send,
    emit(raw: string) { onMessage?.({ data: raw } as MessageEvent); },
    enabledWhenAdded,
    track,
    connection,
    dependencies: {
      peerConnection: () => connection,
      microphone: () => Promise.resolve(stream),
      audio: () => document.createElement("audio"),
    },
  };
}

describe("browser realtime session", () => {
  it("enables the microphone only after acknowledgement activates the call", async () => {
    const browser = browserHarness();
    let resolveAck!: () => void;
    const acknowledgement = new Promise<void>((resolve) => { resolveAck = resolve; });
    const acknowledge = vi.fn(() => acknowledgement);
    const session = createBrowserRealtimeSessionFactory({
      exchangeSdp: () => {
        expect(browser.track.enabled).toBe(false);
        return Promise.resolve({
          answerSdp: "v=0\r\nanswer", attemptId: "attempt-1",
          deadlineAt: new Date(Date.now() + 60_000).toISOString(),
        });
      },
      acknowledge,
      requestEnd: () => Promise.resolve(),
    }, browser.dependencies).create("session-1", "csrf");

    const connecting = session.connect();
    await vi.waitFor(() => expect(acknowledge).toHaveBeenCalledOnce());
    expect(browser.enabledWhenAdded).toEqual([false]);
    expect(session.state).toBe("connecting");
    expect(browser.track.enabled).toBe(false);
    expect(browser.send).not.toHaveBeenCalled();
    resolveAck();
    await connecting;
    expect(browser.track.enabled).toBe(true);
    expect(browser.send).toHaveBeenCalledExactlyOnceWith(JSON.stringify({ type: "response.create" }));
    await session.end("learner_ended");
  });

  it("exchanges SDP, acknowledges, and releases media when ended", async () => {
    const browser = browserHarness();
    const events: string[] = [];
    const factory = createBrowserRealtimeSessionFactory({
      exchangeSdp: (sessionId, csrfToken, offer) => {
        expect([sessionId, csrfToken, offer]).toEqual(["session-1", "csrf", "v=0\r\noffer"]);
        events.push("exchange");
        return Promise.resolve({ answerSdp: "v=0\r\nanswer", attemptId: "attempt-1", deadlineAt: new Date(Date.now() + 60_000).toISOString() });
      },
      acknowledge: () => { events.push("ack"); return Promise.resolve(); },
      requestEnd: () => { events.push("end"); return Promise.resolve(); },
    }, browser.dependencies);
    const session = factory.create("session-1", "csrf");
    await session.connect();
    expect(session.state).toBe("connected");
    expect(events).toEqual(["exchange", "ack"]);
    await session.end("learner_ended");
    expect(session.state).toBe("ended");
    expect(events).toEqual(["exchange", "ack", "end"]);
    expect(browser.stop).toHaveBeenCalledOnce();
    expect(browser.close).toHaveBeenCalledOnce();
  });

  it("requests server cleanup when acknowledgement fails", async () => {
    const browser = browserHarness();
    const requestEnd = vi.fn(async () => {});
    const session = createBrowserRealtimeSessionFactory({
      exchangeSdp: () => Promise.resolve({
        answerSdp: "v=0\r\nanswer", attemptId: "attempt-2",
        deadlineAt: new Date(Date.now() + 60_000).toISOString(),
      }),
      acknowledge: () => Promise.reject(new Error("ack failed")),
      requestEnd,
    }, browser.dependencies).create("session-2", "csrf");
    await expect(session.connect()).rejects.toThrow("ack failed");
    expect(session.state).toBe("failed");
    expect(requestEnd).toHaveBeenCalledOnce();
    expect(browser.send).not.toHaveBeenCalled();
    expect(browser.track.enabled).toBe(false);
    expect(browser.stop).toHaveBeenCalledOnce();
    expect(browser.close).toHaveBeenCalledOnce();
  });

  it("shows finalized transcript turns in item order without duplicates", async () => {
    const browser = browserHarness();
    const session = createBrowserRealtimeSessionFactory({
      exchangeSdp: () => Promise.resolve({
        answerSdp: "v=0\r\nanswer", attemptId: "attempt-3",
        deadlineAt: new Date(Date.now() + 600_000).toISOString(),
      }),
      acknowledge: () => Promise.resolve(),
      requestEnd: () => Promise.resolve(),
    }, browser.dependencies).create("session-3", "csrf");
    const transcript = vi.fn();
    session.subscribeTranscript(transcript);
    await session.connect();
    browser.emit(JSON.stringify({ type: "conversation.item.added", item: { id: "learner-1", role: "user" } }));
    browser.emit(JSON.stringify({ type: "response.output_item.added", item: { id: "tutor-1", role: "assistant" } }));
    browser.emit(JSON.stringify({ type: "response.output_audio_transcript.done", item_id: "tutor-1", transcript: "こんにちは" }));
    browser.emit(JSON.stringify({ type: "conversation.item.input_audio_transcription.completed", item_id: "learner-1", transcript: "Hello" }));
    browser.emit(JSON.stringify({ type: "conversation.item.input_audio_transcription.completed", item_id: "learner-1", transcript: "duplicate" }));
    expect(transcript).toHaveBeenLastCalledWith([
      { itemId: "learner-1", role: "learner", text: "Hello" },
      { itemId: "tutor-1", role: "tutor", text: "こんにちは" },
    ]);
    await session.end("learner_ended");
  });
});

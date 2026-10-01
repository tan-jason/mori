import { describe, expect, it, vi } from "vitest";
import { createBrowserRealtimeSessionFactory } from "./browser-realtime-session";

function browserHarness() {
  const stop = vi.fn();
  const close = vi.fn();
  const track = { stop } as unknown as MediaStreamTrack;
  const stream = {
    getAudioTracks: () => [track],
    getTracks: () => [track],
  } as unknown as MediaStream;
  const connection = {
    iceGatheringState: "complete",
    connectionState: "connected",
    localDescription: { type: "offer", sdp: "v=0\r\noffer" },
    addTrack: vi.fn(),
    createDataChannel: () => ({ readyState: "open" }),
    createOffer: () => Promise.resolve({ type: "offer", sdp: "v=0\r\noffer" }),
    setLocalDescription: vi.fn(async () => {}),
    setRemoteDescription: vi.fn(async () => {}),
    close,
  } as unknown as RTCPeerConnection;
  return {
    stop,
    close,
    connection,
    dependencies: {
      peerConnection: () => connection,
      microphone: () => Promise.resolve(stream),
      audio: () => document.createElement("audio"),
    },
  };
}

describe("browser realtime session", () => {
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
    expect(browser.stop).toHaveBeenCalledOnce();
    expect(browser.close).toHaveBeenCalledOnce();
  });
});

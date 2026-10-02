import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";
import { useLearnerSession } from "../../app/use-learner-session";
import { BASE_LANGUAGE } from "../../domain/languages";
import type { PlannedSession } from "../../domain/session";
import {
  unconfiguredRealtimeSessionFactory,
  type RealtimeSession,
  type RealtimeSessionState,
  type TranscriptTurn,
} from "../../realtime/realtime-session";

function requestedWordsFromInput(value: string): string[] {
  const words = value.split(",").map((word) => word.trim().replace(/\s+/g, " ")).filter(Boolean);
  if (words.length > 8 || words.some((word) => word.length > 48)) {
    throw new Error("Add up to eight words, each under 48 characters.");
  }
  if (new Set(words.map((word) => word.toLocaleLowerCase())).size !== words.length) {
    throw new Error("Remove repeated words before starting.");
  }
  return words;
}

const terminalStates = new Set(["setup_failed", "analysis_pending", "analysis_failed", "ready"]);

function reservationExpired(session: PlannedSession): boolean {
  return Date.parse(session.reservationExpiresAt) <= Date.now();
}

function formatTime(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function SessionPage() {
  const { gateway, realtime = unconfiguredRealtimeSessionFactory } = useAppDependencies();
  const { targetLanguage } = useLanguageProfile();
  const { learner } = useLearnerSession();
  const [topic, setTopic] = useState("");
  const [requestedWords, setRequestedWords] = useState("");
  const [planned, setPlanned] = useState<PlannedSession | null>(null);
  const [connectionState, setConnectionState] = useState<RealtimeSessionState>("idle");
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [voiceAvailability, setVoiceAvailability] = useState<{ available: boolean; maxCallSeconds: number } | null>(null);
  const [retryBlocked, setRetryBlocked] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [transcript, setTranscript] = useState<readonly TranscriptTurn[]>([]);
  const [microphoneMuted, setMicrophoneMuted] = useState(false);
  const idempotencyKey = useRef<string | null>(null);
  const activeSession = useRef<RealtimeSession | null>(null);
  const unsubscribeCall = useRef<(() => void) | null>(null);
  const unsubscribeTranscript = useRef<(() => void) | null>(null);
  const transcriptList = useRef<HTMLOListElement | null>(null);
  const followTranscript = useRef(true);

  useEffect(() => {
    if (!realtime.available) return;
    const controller = new AbortController();
    const check = () => {
      void gateway.getVoiceAvailability(controller.signal)
        .then((availability) => {
          if (!controller.signal.aborted) setVoiceAvailability(availability);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setVoiceAvailability({ available: false, maxCallSeconds: 0 });
          }
        });
    };
    check();
    const interval = window.setInterval(check, 5000);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [gateway, realtime]);

  const voiceEnabled = realtime.available && voiceAvailability?.available === true;
  const plannedId = planned?.id;

  useEffect(() => {
    if (connectionState !== "connected" && connectionState !== "reconnecting") return;
    const deadlineAt = activeSession.current?.deadlineAt;
    if (!deadlineAt) return;
    const update = () => setRemainingSeconds(Math.max(0, Math.ceil((Date.parse(deadlineAt) - Date.now()) / 1000)));
    update();
    const interval = window.setInterval(update, 250);
    return () => window.clearInterval(interval);
  }, [connectionState]);

  useEffect(() => {
    const list = transcriptList.current;
    if (list && followTranscript.current) list.scrollTop = list.scrollHeight;
  }, [transcript]);

  useEffect(() => {
    if (!plannedId || !["ending", "ended", "failed"].includes(connectionState)) return;
    const controller = new AbortController();
    const poll = () => {
      void gateway.getSession(plannedId, controller.signal).then((current) => {
        if (controller.signal.aborted) return;
        if (current.state === "setup_failed" || (current.state === "planned" && reservationExpired(current))) {
          setPlanned(null);
          idempotencyKey.current = null;
        } else {
          setPlanned(current);
        }
        if (terminalStates.has(current.state)) window.clearInterval(interval);
      }).catch(() => {});
    };
    const interval = window.setInterval(poll, 2000);
    poll();
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [gateway, plannedId, connectionState]);

  useEffect(() => () => {
    unsubscribeCall.current?.();
    unsubscribeTranscript.current?.();
    if (activeSession.current && ["connecting", "connected", "reconnecting"].includes(activeSession.current.state)) {
      void activeSession.current.end("learner_ended");
    }
  }, []);

  const begin = async () => {
    if (!voiceEnabled || retryBlocked || isStarting || connectionState === "connected") return;
    setError("");
    setIsStarting(true);
    let sessionId: string | null = null;
    try {
      const words = requestedWordsFromInput(requestedWords);
      const normalizedTopic = topic.trim().replace(/\s+/g, " ");
      if (normalizedTopic.length > 160) throw new Error("Keep your topic under 160 characters.");
      const reusablePlan = planned?.state === "planned" && !reservationExpired(planned) ? planned : null;
      if (planned && !reusablePlan) {
        setPlanned(null);
        idempotencyKey.current = null;
      }
      idempotencyKey.current ??= crypto.randomUUID();
      const session = reusablePlan ?? await gateway.createSession({
        languageProfileId: learner.activeLanguageProfile.id,
        topic: normalizedTopic || null,
        requestedWords: words,
        idempotencyKey: idempotencyKey.current,
        csrfToken: learner.csrfToken,
      });
      setPlanned(session);
      sessionId = session.id;
      const call = realtime.create(session.id, learner.csrfToken);
      unsubscribeCall.current?.();
      unsubscribeTranscript.current?.();
      activeSession.current = call;
      call.setMicrophoneMuted(microphoneMuted);
      setRemainingSeconds(null);
      setTranscript([]);
      followTranscript.current = true;
      unsubscribeCall.current = call.subscribe(setConnectionState);
      unsubscribeTranscript.current = call.subscribeTranscript(setTranscript);
      await call.connect();
    } catch (reason) {
      setError(reason instanceof Error && reason.name === "NotAllowedError"
        ? "Microphone access was blocked. Allow it in your browser, then try again."
        : reason instanceof Error ? reason.message : "We could not start your conversation.");
      if (sessionId) {
        try {
          const current = await gateway.getSession(sessionId);
          if (current.state === "setup_failed" || (current.state === "planned" && reservationExpired(current))) {
            setPlanned(null);
            idempotencyKey.current = null;
          } else if (current.state !== "planned") {
            setRetryBlocked(true);
          } else {
            setPlanned(current);
          }
        } catch {
          setRetryBlocked(true);
        }
      }
    } finally {
      setIsStarting(false);
    }
  };

  const end = async () => {
    setError("");
    try {
      await activeSession.current?.end("learner_ended");
    } catch {
      setRetryBlocked(true);
      setError("We could not confirm the end of your conversation. Please check its status.");
    }
  };

  const toggleMicrophone = () => {
    if (isStarting || connectionState === "ending" || connectionState === "ended") return;
    const call = activeSession.current;
    const nextMuted = !microphoneMuted;
    if (call && (call.state === "connected" || call.state === "reconnecting")) {
      call.setMicrophoneMuted(nextMuted);
    }
    setMicrophoneMuted(nextMuted);
  };

  const statusLabel = planned?.state === "analysis_pending" || planned?.state === "ready"
    ? "Conversation saved"
    : planned?.state === "analysis_failed"
      ? "Recap unavailable"
      : planned?.state === "setup_failed"
        ? "Connection ended"
        : connectionState === "ended" && planned?.state === "ending"
          ? "Finishing conversation"
          : ({
    idle: "Ready when you are",
    connecting: "Connecting",
    connected: "Connected",
    reconnecting: "Reconnecting",
    ending: "Ending",
    ended: "Session ended",
    failed: "Connection needs attention",
  } as const)[connectionState];
  const callActive = connectionState === "connected" || connectionState === "reconnecting" || connectionState === "ending";
  const beginDisabled = !voiceEnabled || retryBlocked || isStarting || connectionState === "ended" || (planned !== null && planned.state !== "planned");
  const microphoneStatus = !voiceEnabled && connectionState === "idle"
    ? "Microphone unavailable"
    : callActive
      ? microphoneMuted ? "Microphone off" : "Microphone on"
      : microphoneMuted ? "Will start muted" : "Will start unmuted";

  return (
    <div className="session-page">
      <div className="session-topbar">
        <Link className="back-link" to="/">
          <span aria-hidden="true">←</span> Back home
        </Link>
        <span className="connection-status">
          <span aria-hidden="true" /> {voiceEnabled || connectionState !== "idle" ? statusLabel : "Voice unavailable"}
        </span>
      </div>

      <section className="session-stage" aria-labelledby="session-title">
        <div className="session-stage-copy">
          <p className="eyebrow">{callActive ? "Your conversation" : "Before your conversation"}</p>
          <h1 id="session-title">Make a little room to speak.</h1>
          <p>
            Find a quiet spot and give yourself permission to be imperfect. Mori will
            keep the conversation in {targetLanguage.name} and help when you get
            stuck.
          </p>

          <div className="language-pair" aria-label="Language pair">
            <div className="language-pair-value">
              <span>Base language</span>
              <strong>{BASE_LANGUAGE.name}</strong>
            </div>
            <span className="language-arrow" aria-hidden="true">
              →
            </span>
            <div className="language-pair-value">
              <span>Learning</span>
              <strong>{targetLanguage.courseName}</strong>
              <small>{targetLanguage.nativeName}</small>
            </div>
          </div>

          {planned && (
            <div className="session-plan-preview" role="status">
              <strong>Your conversation focus</strong>
              <ul>{planned.planPreview.objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul>
            </div>
          )}

          {!voiceEnabled && connectionState === "idle" && (
            <div className="foundation-notice" role="note">
              <strong>Voice practice is unavailable</strong>
              <p>Your language and tutor preferences are ready. Speaking will open here when voice access is available.</p>
            </div>
          )}
          {error && <p className="session-error" role="alert">{error}</p>}
          {callActive && (
            <div className="session-limit session-limit-active">
              <span className="session-limit-time" role="timer" aria-label="Time remaining">
                {remainingSeconds !== null ? formatTime(remainingSeconds) : "--:--"}
              </span>
              <span>Time remaining</span>
            </div>
          )}

          <div className="session-call-controls">
            <div className="session-call-actions">
              {callActive ? (
                <button className="button button-light" type="button" onClick={() => void end()} disabled={connectionState === "ending"}>
                  {connectionState === "ending" ? "Ending conversation…" : "End conversation"}
                </button>
              ) : (
                <button className="button button-primary" type="button" onClick={() => void begin()} disabled={beginDisabled}>
                  {isStarting ? "Starting conversation…" : connectionState === "failed" ? "Try again" : "Begin session"}
                </button>
              )}
              <button
                className={`session-microphone-button${microphoneMuted ? " session-microphone-button-muted" : ""}`}
                type="button"
                aria-label={microphoneMuted ? "Unmute microphone" : "Mute microphone"}
                onClick={toggleMicrophone}
                disabled={callActive ? connectionState === "ending" : beginDisabled}
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="2" width="6" height="12" rx="3" />
                  <path d="M5 10a7 7 0 0 0 14 0M12 17v4m-4 0h8" />
                  {microphoneMuted && <path d="M3 3l18 18" />}
                </svg>
              </button>
            </div>
            <p className="session-microphone-status" role="status">
              {microphoneStatus}
            </p>
          </div>
        </div>

        {(callActive || transcript.length > 0) && (
          <section className="session-transcript" aria-labelledby="session-transcript-title">
            <div className="session-transcript-heading">
              <p className="eyebrow">Conversation notes</p>
              <h2 id="session-transcript-title">Transcript</h2>
            </div>
            {transcript.length === 0 ? (
              <p className="session-transcript-empty">Your conversation will appear here as you speak.</p>
            ) : (
              <ol
                className="session-transcript-list"
                ref={transcriptList}
                onScroll={(event) => {
                  const list = event.currentTarget;
                  followTranscript.current = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
                }}
              >
                {transcript.map((turn) => (
                  <li key={turn.itemId} className={`session-transcript-turn session-transcript-turn-${turn.role}`}>
                    <span>{turn.role === "learner" ? "You" : "Mori"}</span>
                    <p>{turn.text}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}

        <aside className="session-preferences" aria-labelledby="preferences-title">
          <p className="eyebrow">Session setup</p>
          <h2 id="preferences-title">Your preferences</h2>

          <div className="preference-row">
            <div>
              <strong>Corrections</strong>
              <span>{learner.preferences.correctionPreference}</span>
            </div>
            <Link className="preference-link" to="/profile" aria-label="Change corrections">
              Change
            </Link>
          </div>

          <div className="preference-row">
            <div>
              <strong>Tutor pace</strong>
              <span>{learner.preferences.tutorPace}</span>
            </div>
            <Link className="preference-link" to="/profile" aria-label="Change tutor pace">Change</Link>
          </div>

          <label className="session-setup-field">
            <span>
              <strong>Something you want to talk about</strong>
              <small>Optional. Mori can choose a starting topic with you.</small>
            </span>
            <input value={topic} onChange={(event) => { setTopic(event.target.value); idempotencyKey.current = null; }} disabled={planned !== null} maxLength={160} placeholder="For example, my weekend" />
          </label>

          <label className="session-setup-field">
            <span>
              <strong>Words to practice</strong>
              <small>Optional. Separate up to eight words with commas.</small>
            </span>
            <input value={requestedWords} onChange={(event) => { setRequestedWords(event.target.value); idempotencyKey.current = null; }} disabled={planned !== null} placeholder="For example, market, recipe" />
          </label>

          {!callActive && (
            <div className="session-limit">
              <span className="session-limit-time">{voiceAvailability?.maxCallSeconds ? formatTime(voiceAvailability.maxCallSeconds) : "--:--"}</span>
              <span>Maximum call time</span>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}

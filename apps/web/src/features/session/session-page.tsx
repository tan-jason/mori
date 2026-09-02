import { useState } from "react";
import { Link } from "react-router-dom";

export function SessionPage() {
  const [captionsEnabled, setCaptionsEnabled] = useState(false);
  const [playbackRate, setPlaybackRate] = useState("0.82");

  return (
    <div className="session-page">
      <div className="session-topbar">
        <Link className="back-link" to="/">
          <span aria-hidden="true">←</span> Back home
        </Link>
        <span className="connection-status">
          <span aria-hidden="true" /> Not connected
        </span>
      </div>

      <section className="session-stage" aria-labelledby="session-title">
        <div className="session-stage-copy">
          <p className="eyebrow">Before your conversation</p>
          <h1 id="session-title">Make a little room to speak.</h1>
          <p>
            Find a quiet spot and give yourself permission to be imperfect. Mori will
            keep the conversation in Mandarin and help when you get stuck.
          </p>

          <div className="language-pair" aria-label="Language pair">
            <label>
              <span>Base language</span>
              <select disabled defaultValue="English">
                <option>English</option>
              </select>
            </label>
            <span className="language-arrow" aria-hidden="true">
              →
            </span>
            <label>
              <span>Learning</span>
              <select disabled defaultValue="Standard Mandarin">
                <option>Standard Mandarin</option>
              </select>
            </label>
          </div>

          <div className="foundation-notice" role="note">
            <strong>Connection scaffold only</strong>
            <p>
              Microphone access and the realtime agent are intentionally not wired in
              this foundation.
            </p>
          </div>

          <button
            className="button button-primary button-wide"
            type="button"
            disabled
            title="Realtime integration is not configured"
          >
            Begin session
          </button>
        </div>

        <aside className="session-preferences" aria-labelledby="preferences-title">
          <p className="eyebrow">Session setup</p>
          <h2 id="preferences-title">Your preferences</h2>

          <div className="preference-row">
            <div>
              <strong>Corrections</strong>
              <span>Balanced</span>
            </div>
            <button type="button" disabled>
              Change
            </button>
          </div>

          <label className="preference-field">
            <span>
              <strong>Tutor pace</strong>
              <small>Set for your current level</small>
            </span>
            <select
              value={playbackRate}
              onChange={(event) => setPlaybackRate(event.target.value)}
            >
              <option value="0.75">Gentle · 0.75x</option>
              <option value="0.82">Steady · 0.82x</option>
              <option value="0.9">Natural · 0.90x</option>
            </select>
          </label>

          <label className="toggle-row">
            <span>
              <strong>Live captions</strong>
              <small>Show conversation text on screen</small>
            </span>
            <input
              type="checkbox"
              checked={captionsEnabled}
              onChange={(event) => setCaptionsEnabled(event.target.checked)}
            />
          </label>

          <div className="session-limit">
            <span className="session-limit-time">20:00</span>
            <span>Maximum connected time</span>
          </div>
        </aside>
      </section>
    </div>
  );
}

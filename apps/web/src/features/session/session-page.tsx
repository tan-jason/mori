import { useState } from "react";
import { Link } from "react-router-dom";
import { useLanguageProfile } from "../../app/use-language-profile";
import { BASE_LANGUAGE } from "../../domain/languages";

export function SessionPage() {
  const { targetLanguage } = useLanguageProfile();
  const [captionsEnabled, setCaptionsEnabled] = useState(false);
  const [playbackRate, setPlaybackRate] = useState("0.82");

  return (
    <div className="session-page">
      <div className="session-topbar">
        <Link className="back-link" to="/">
          <span aria-hidden="true">←</span> Back home
        </Link>
        <span className="connection-status">
          <span aria-hidden="true" /> Preview mode
        </span>
      </div>

      <section className="session-stage" aria-labelledby="session-title">
        <div className="session-stage-copy">
          <p className="eyebrow">Before your conversation</p>
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

          <div className="foundation-notice" role="note">
            <strong>Voice practice is coming soon</strong>
            <p>
              Mori is still getting the microphone ready. You can set your
              preferences now and start speaking when voice access is available.
            </p>
          </div>

          <button
            className="button button-primary button-wide"
            type="button"
            disabled
            title="Voice practice is not available in this preview"
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
            <Link className="preference-link" to="/profile">
              Change
            </Link>
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

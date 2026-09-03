import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useLanguageProfile } from "../../app/use-language-profile";
import { BASE_LANGUAGE } from "../../domain/languages";

const timezones = [
  { value: "America/New_York", label: "Eastern Time (US & Canada)" },
  { value: "America/Chicago", label: "Central Time (US & Canada)" },
  { value: "America/Denver", label: "Mountain Time (US & Canada)" },
  { value: "America/Los_Angeles", label: "Pacific Time (US & Canada)" },
  { value: "Europe/London", label: "London" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Asia/Shanghai", label: "China Standard Time" },
];

export function ProfilePage() {
  const { targetLanguage } = useLanguageProfile();
  const [name, setName] = useState("Jason Tan");
  const [correctionPreference, setCorrectionPreference] = useState("balanced");
  const [pace, setPace] = useState("level");
  const [timezone, setTimezone] = useState("America/New_York");
  const [saved, setSaved] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const markChanged = () => {
    setSaved(false);
    setIsDirty(true);
  };
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaved(true);
    setIsDirty(false);
  };

  return (
    <div className="detail-page profile-page">
      <header className="profile-hero">
        <div className="profile-avatar" aria-hidden="true">
          JT
        </div>
        <div>
          <p className="eyebrow">Learner profile</p>
          <h1>Your learning setup</h1>
          <p>
            Keep your account details and tutor preferences up to date. Your learning
            progress stays with this language profile.
          </p>
        </div>
      </header>

      <form className="profile-form" onSubmit={handleSubmit}>
        <section className="settings-card" aria-labelledby="account-settings-title">
          <div className="settings-card-heading">
            <span className="settings-number" aria-hidden="true">01</span>
            <div>
              <p className="eyebrow">Account</p>
              <h2 id="account-settings-title">About you</h2>
            </div>
          </div>

          <div className="profile-fields profile-fields-two">
            <label className="form-field">
              <span>Full name</span>
              <input
                type="text"
                aria-label="Full name"
                autoComplete="name"
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  markChanged();
                }}
              />
              <small>This is how Mori will greet you.</small>
            </label>

            <label className="form-field">
              <span>Email</span>
              <input
                className="readonly-field"
                type="email"
                aria-label="Email"
                autoComplete="email"
                value="jason.tan@gmail.com"
                readOnly
                aria-describedby="email-help"
              />
              <small id="email-help">Managed by your Google account.</small>
            </label>
          </div>
        </section>

        <section className="settings-card" aria-labelledby="language-settings-title">
          <div className="settings-card-heading">
            <span className="settings-number" aria-hidden="true">02</span>
            <div>
              <p className="eyebrow">Language profile</p>
              <h2 id="language-settings-title">Your learning path</h2>
            </div>
            <span className="profile-status">Active</span>
          </div>

          <div className="profile-fields profile-fields-two">
            <label className="form-field">
              <span>Base language</span>
              <select
                disabled
                value={BASE_LANGUAGE.id}
                aria-label="Base language"
                aria-describedby="language-help"
              >
                <option value={BASE_LANGUAGE.id}>{BASE_LANGUAGE.name}</option>
              </select>
            </label>

            <label className="form-field">
              <span>Language to learn</span>
              <select
                disabled
                value={targetLanguage.id}
                aria-label="Language to learn"
                aria-describedby="language-help"
              >
                <option value={targetLanguage.id}>
                  {targetLanguage.courseName} · {targetLanguage.nativeName}
                </option>
              </select>
            </label>
          </div>

          <p className="form-note" id="language-help">
            Progress is tracked separately for each language. To switch languages,
            start a new learning profile.
          </p>

          <div className="level-summary">
            <span className="level-summary-mark" aria-hidden="true">
              {targetLanguage.mark}
            </span>
            <div>
              <small>Current assessed level</small>
              <strong>Learning Beginner</strong>
              <p>Short, familiar exchanges with a little support.</p>
            </div>
            <span className="evidence-label">Set by conversation evidence</span>
          </div>
        </section>

        <section className="settings-card" aria-labelledby="tutor-settings-title">
          <div className="settings-card-heading">
            <span className="settings-number" aria-hidden="true">03</span>
            <div>
              <p className="eyebrow">Conversation style</p>
              <h2 id="tutor-settings-title">Tutor preferences</h2>
            </div>
          </div>

          <div className="profile-fields profile-fields-two">
            <label className="form-field">
              <span>Corrections</span>
              <select
                value={correctionPreference}
                aria-label="Corrections"
                onChange={(event) => {
                  setCorrectionPreference(event.target.value);
                  markChanged();
                }}
              >
                <option value="light">Light - keep conversation flowing</option>
                <option value="balanced">Balanced - correct useful moments</option>
                <option value="frequent">Frequent - correct more often</option>
              </select>
              <small>Meaning-blocking errors are always addressed.</small>
            </label>

            <label className="form-field">
              <span>Default tutor pace</span>
              <select
                value={pace}
                aria-label="Default tutor pace"
                onChange={(event) => {
                  setPace(event.target.value);
                  markChanged();
                }}
              >
                <option value="level">Adapt to my level - recommended</option>
                <option value="gentle">Gentle - 0.75x</option>
                <option value="steady">Steady - 0.82x</option>
                <option value="natural">Natural - 0.90x</option>
              </select>
              <small>You can still ask Mori to slow down during a session.</small>
            </label>

            <label className="form-field profile-field-wide">
              <span>Local timezone</span>
              <select
                value={timezone}
                aria-label="Local timezone"
                onChange={(event) => {
                  setTimezone(event.target.value);
                  markChanged();
                }}
              >
                {timezones.map((item) => (
                  <option value={item.value} key={item.value}>{item.label}</option>
                ))}
              </select>
              <small>Used for natural greetings and weekly plan resets.</small>
            </label>
          </div>
        </section>

        <div className="profile-actions">
          <span className="save-status" role="status" aria-live="polite">
            {saved
              ? "Preferences saved for this preview."
              : isDirty
                ? "You have unsaved changes."
                : "Your preferences are up to date."}
          </span>
          <button
            className="button button-primary"
            type="submit"
            disabled={!isDirty}
          >
            Save changes
          </button>
        </div>
      </form>

      <section className="account-data" aria-labelledby="account-data-title">
        <div>
          <p className="eyebrow">Privacy controls</p>
          <h2 id="account-data-title">Your data</h2>
          <p>Review what Mori remembers or manage your account data.</p>
        </div>
        <div className="account-data-actions">
          <Link className="button account-button" to="/memories">Review memories</Link>
          <button className="button account-button" type="button" disabled title="Transcript exports are not available in this preview">Export transcripts</button>
          <Link className="button account-button account-signout" to="/login">Sign out</Link>
        </div>
      </section>
    </div>
  );
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, isAuthenticationRequired } from "../../api/api-error";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";
import { useLearnerSession } from "../../app/use-learner-session";
import type {
  CorrectionPreference,
  TutorPace,
} from "../../domain/identity";
import { getInitials } from "../../domain/identity";
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
  const { gateway } = useAppDependencies();
  const { targetLanguage } = useLanguageProfile();
  const { learner, replaceLearner } = useLearnerSession();
  const learning = learner.activeLanguageProfile.learning;
  const levelLabel = learning.mode === "practice"
    ? "Fluent conversation"
    : `Learning ${(learning.provisionalLevel ?? "beginner")[0]?.toUpperCase()}${(learning.provisionalLevel ?? "beginner").slice(1)}`;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [correctionPreference, setCorrectionPreference] =
    useState<CorrectionPreference>(learner.preferences.correctionPreference);
  const [pace, setPace] = useState<TutorPace>(learner.preferences.tutorPace);
  const [timezone, setTimezone] = useState(learner.preferences.timezone);
  const [learningGoal, setLearningGoal] = useState(learner.preferences.learningGoal);
  const [speakingContext, setSpeakingContext] = useState(learner.preferences.speakingContext);
  const [learningNotes, setLearningNotes] = useState(learner.preferences.learningNotes);
  const [intentError, setIntentError] = useState("");
  const [saved, setSaved] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const timezoneOptions = timezones.some((item) => item.value === timezone)
    ? timezones
    : [...timezones, { value: timezone, label: timezone }];

  const savePreferences = useMutation({
    mutationFn: () =>
      gateway.updatePreferences({
        changes: {
          correctionPreference, tutorPace: pace, timezone,
          learningGoal: learningGoal.trim(),
          speakingContext: speakingContext.trim(),
          learningNotes: learningNotes.trim(),
        },
        expectedVersion: learner.preferences.version,
        csrfToken: learner.csrfToken,
      }),
    onSuccess: (updatedLearner) => {
      if (updatedLearner.preferences) {
        setLearningGoal(updatedLearner.preferences.learningGoal);
        setSpeakingContext(updatedLearner.preferences.speakingContext);
        setLearningNotes(updatedLearner.preferences.learningNotes);
      }
      setSaved(true);
      setIsDirty(false);
      replaceLearner(updatedLearner);
    },
    onError: (error) => {
      if (isAuthenticationRequired(error)) {
        queryClient.clear();
        void navigate("/login", { replace: true });
      }
    },
  });
  const signOut = useMutation({
    mutationFn: () => gateway.logout(learner.csrfToken),
    onSuccess: () => {
      queryClient.clear();
      void navigate("/login", { replace: true });
    },
    onError: (error) => {
      if (isAuthenticationRequired(error)) {
        queryClient.clear();
        void navigate("/login", { replace: true });
      }
    },
  });

  const markChanged = () => {
    savePreferences.reset();
    setIntentError("");
    setSaved(false);
    setIsDirty(true);
  };
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!learningGoal.trim() || !speakingContext.trim()) {
      setIntentError("Add your learning goal and speaking context before saving.");
      return;
    }
    if (learningGoal.length + speakingContext.length + learningNotes.length > 3000) {
      setIntentError("Keep your learning details within 3,000 characters.");
      return;
    }
    if (isDirty && !savePreferences.isPending) {
      savePreferences.mutate();
    }
  };

  return (
    <div className="detail-page profile-page">
      <header className="profile-hero">
        <div className="profile-avatar" aria-hidden="true">
          {getInitials(learner.user.displayName)}
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
                className="readonly-field"
                type="text"
                aria-label="Full name"
                autoComplete="name"
                value={learner.user.displayName}
                readOnly
                aria-describedby="name-help"
              />
              <small id="name-help">Managed by your Google account.</small>
            </label>

            <label className="form-field">
              <span>Email</span>
              <input
                className="readonly-field"
                type="email"
                aria-label="Email"
                autoComplete="email"
                value={learner.user.email}
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
              <small>{learning.mode === "practice" ? "Practice mode" : "Provisional starting level"}</small>
              <strong>{levelLabel}</strong>
              <p>{learning.mode === "practice"
                ? "Natural conversation without unsolicited learning advice."
                : "Mori will use conversation evidence to understand your level."}</p>
            </div>
            <span className="evidence-label">Your starting choice</span>
          </div>
        </section>

        <section className="settings-card" aria-labelledby="learning-goals-title">
          <div className="settings-card-heading">
            <span className="settings-number" aria-hidden="true">03</span>
            <div><p className="eyebrow">Your purpose</p><h2 id="learning-goals-title">Learning goals</h2></div>
          </div>
          <p className="form-note">Mori uses these details to choose useful situations for your conversations.</p>
          <div className="profile-fields">
            <label className="form-field"><span>Your learning goal</span><textarea aria-label="Your learning goal" required maxLength={500} value={learningGoal} disabled={savePreferences.isPending} onChange={(event) => { setLearningGoal(event.target.value); markChanged(); }} /><small>What would you like to be able to do?</small></label>
            <label className="form-field"><span>Who you will speak with and how</span><textarea aria-label="Who you will speak with and how" required maxLength={500} value={speakingContext} disabled={savePreferences.isPending} onChange={(event) => { setSpeakingContext(event.target.value); markChanged(); }} /><small>Describe the people and the tone you want to use.</small></label>
            <label className="form-field"><span>Anything else Mori should know? (optional)</span><textarea aria-label="Anything else Mori should know?" maxLength={3000} value={learningNotes} disabled={savePreferences.isPending} onChange={(event) => { setLearningNotes(event.target.value); markChanged(); }} /><small>Learning details: {learningGoal.length + speakingContext.length + learningNotes.length} of 3,000 characters. Keep your answers brief.</small></label>
          </div>
          {intentError ? <p className="onboarding-error" role="alert">{intentError}</p> : null}
        </section>

        <section className="settings-card" aria-labelledby="tutor-settings-title">
          <div className="settings-card-heading">
            <span className="settings-number" aria-hidden="true">04</span>
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
                disabled={savePreferences.isPending}
                onChange={(event) => {
                  setCorrectionPreference(
                    event.target.value as CorrectionPreference,
                  );
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
                disabled={savePreferences.isPending}
                onChange={(event) => {
                  setPace(event.target.value as TutorPace);
                  markChanged();
                }}
              >
                <option value="level">Adapt to my level - recommended</option>
                <option value="gentle">Gentle - slower practice speech</option>
                <option value="steady">Steady - clear and unhurried</option>
                <option value="natural">Natural - conversational pace</option>
              </select>
              <small>Gentle asks Mori to slow the language you are learning. You can ask for shorter phrases or longer pauses.</small>
            </label>

            <label className="form-field profile-field-wide">
              <span>Local timezone</span>
              <select
                value={timezone}
                aria-label="Local timezone"
                disabled={savePreferences.isPending}
                onChange={(event) => {
                  setTimezone(event.target.value);
                  markChanged();
                }}
              >
                {timezoneOptions.map((item) => (
                  <option value={item.value} key={item.value}>{item.label}</option>
                ))}
              </select>
              <small>Used for natural greetings and weekly plan resets.</small>
            </label>
          </div>
        </section>

        <div className="profile-actions">
          <span
            className={`save-status${savePreferences.isError ? " save-status-error" : ""}`}
            role="status"
            aria-live="polite"
          >
            {savePreferences.isPending
              ? "Saving your preferences..."
              : savePreferences.isError
                ? savePreferences.error instanceof ApiError &&
                  savePreferences.error.code === "preference_version_conflict"
                  ? "These preferences changed elsewhere. Refresh the page before saving."
                  : savePreferences.error instanceof ApiError && savePreferences.error.status === 422
                    ? "Check your learning details. Shorten them if they are too long, then try again."
                  : "We could not save your preferences. Please try again."
                : saved
                  ? "Preferences saved."
                  : isDirty
                    ? "You have unsaved changes."
                    : "Your preferences are up to date."}
          </span>
          <button
            className="button button-primary"
            type="submit"
            disabled={!isDirty || savePreferences.isPending}
          >
            {savePreferences.isPending ? "Saving..." : "Save changes"}
          </button>
        </div>
      </form>

      <section className="account-data" aria-labelledby="account-data-title">
        <div>
          <p className="eyebrow">Privacy controls</p>
          <h2 id="account-data-title">Your data</h2>
          <p>Review what Mori remembers or manage your account data.</p>
          {signOut.isError ? (
            <p className="account-action-error" role="alert">
              We could not sign you out. Please try again.
            </p>
          ) : null}
        </div>
        <div className="account-data-actions">
          <Link className="button account-button" to="/memories">Review memories</Link>
          <button className="button account-button" type="button" disabled title="Transcript exports are not available yet">Export transcripts</button>
          <button
            className="button account-button account-signout"
            type="button"
            disabled={signOut.isPending}
            onClick={() => signOut.mutate()}
          >
            {signOut.isPending ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </section>
    </div>
  );
}

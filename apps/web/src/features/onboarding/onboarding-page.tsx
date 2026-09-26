import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, isAuthenticationRequired } from "../../api/api-error";
import { useAppDependencies } from "../../app/app-dependencies";
import { BrandMark } from "../../components/app-shell";
import type {
  CorrectionPreference,
  CurrentLearner,
  LanguagePair,
  StartingChoice,
  TutorPace,
} from "../../domain/identity";

const steps = ["Languages", "Starting point", "Tutor style", "Review"] as const;
const levelChoices: { value: StartingChoice; title: string; description: string }[] = [
  { value: "beginner", title: "Beginner", description: "I know some words or phrases, but conversation is hard." },
  { value: "intermediate", title: "Intermediate", description: "I can talk about familiar, everyday topics." },
  { value: "advanced", title: "Advanced", description: "I can discuss more complex ideas." },
  { value: "unsure", title: "I'm not sure", description: "Start gently, then use conversation to find my level." },
  { value: "fluent", title: "Fluent conversation", description: "I want natural conversation without learning advice." },
];

function parseInterests(value: string): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const part of value.split(/[,\n]/)) {
    const normalized = part.trim().replace(/\s+/g, " ");
    if (!normalized) continue;
    if (normalized.length > 80) throw new Error("Keep each interest under 80 characters.");
    const key = normalized.toLocaleLowerCase();
    if (!seen.has(key)) {
      result.push(normalized);
      seen.add(key);
    }
  }
  if (result.length > 12) throw new Error("Add up to 12 interests.");
  return result;
}

function getTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

interface OnboardingPageProps {
  learner: CurrentLearner;
  onComplete: (learner: CurrentLearner) => void;
}

export function OnboardingPage({ learner, onComplete }: OnboardingPageProps) {
  const { gateway } = useAppDependencies();
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["language-pairs"], queryFn: ({ signal }) => gateway.getLanguagePairs(signal) });
  const [step, setStep] = useState(0);
  const [base, setBase] = useState("");
  const [target, setTarget] = useState("");
  const [startingChoice, setStartingChoice] = useState<StartingChoice | "">("");
  const [corrections, setCorrections] = useState<CorrectionPreference>("balanced");
  const [pace, setPace] = useState<TutorPace>("level");
  const [interestsText, setInterestsText] = useState("");
  const [error, setError] = useState("");
  const idempotencyKey = useRef<string | null>(null);
  const timezone = useRef(getTimezone());

  const pairs = catalog.data ?? [];
  const baseLanguages = [...new Map(pairs.map((pair) => [pair.baseLanguageId, pair.baseLanguageName])).entries()];
  const targets = pairs.filter((pair) => pair.baseLanguageId === base);
  const chosenPair: LanguagePair | undefined = pairs.find(
    (pair) => pair.baseLanguageId === base && pair.targetLanguageId === target,
  );

  const changed = () => {
    setError("");
    idempotencyKey.current = null;
  };

  const createProfile = useMutation({
    mutationFn: async () => {
      if (!startingChoice) throw new Error("Choose a starting point.");
      const interests = parseInterests(interestsText);
      idempotencyKey.current ??= crypto.randomUUID();
      return gateway.createLanguageProfile({
        baseLanguageId: base,
        targetLanguageId: target,
        startingChoice,
        correctionPreference: corrections,
        tutorPace: pace,
        timezone: timezone.current,
        interests,
        idempotencyKey: idempotencyKey.current,
        csrfToken: learner.csrfToken,
      });
    },
    onSuccess: (updatedLearner) => {
      onComplete(updatedLearner);
      void navigate("/", { replace: true });
    },
    onError: (reason) => {
      if (isAuthenticationRequired(reason)) {
        void navigate("/login", { replace: true });
        return;
      }
      if (reason instanceof ApiError && reason.code === "unsupported_language_pair") {
        void catalog.refetch();
        setStep(0);
        setError("That course is no longer available. Choose an available language pair.");
      } else if (reason instanceof ApiError && reason.code === "idempotency_conflict") {
        idempotencyKey.current = null;
        setError("Your setup changed during confirmation. Check your choices and try again.");
      } else {
        setError(reason instanceof Error && !(reason instanceof ApiError)
          ? reason.message
          : "We could not save your setup. Your choices are still here. Please try again.");
      }
    },
  });

  const validateStep = (index: number): boolean => {
    if (index === 0 && (!base || !chosenPair?.available)) {
      setError("Choose both languages from an available course before continuing.");
      return false;
    }
    if (index === 1 && !startingChoice) {
      setError("Choose a starting point before continuing.");
      return false;
    }
    if (index === 2) {
      try {
        parseInterests(interestsText);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Check your interests.");
        return false;
      }
    }
    setError("");
    return true;
  };

  const next = () => {
    if (step < 3) {
      if (validateStep(step)) setStep(step + 1);
      return;
    }
    if ([0, 1, 2].every(validateStep)) createProfile.mutate();
  };

  const goToStep = (destination: number) => {
    if (destination > step) {
      for (let index = step; index < destination; index += 1) {
        if (!validateStep(index)) return;
      }
    }
    setError("");
    setStep(destination);
  };

  return (
    <main className="onboarding-page">
      <div className="onboarding-intro">
        <p className="eyebrow">Welcome to Mori</p>
        <h1>Make a learning profile on purpose.</h1>
        <p>Four short choices before your first conversation. Your progress will stay with the language profile you create.</p>
      </div>

      <section className="onboarding-shell" aria-label="Your learning setup">
        <div className="onboarding-top">
          <div className="brand"><BrandMark /><span className="brand-copy"><strong>Mori</strong><small>Conversation studio</small></span></div>
          <span>Signed in as {learner.user.displayName}</span>
        </div>
        <div className="onboarding-body">
          <aside className="onboarding-side">
            <p className="eyebrow">Your setup</p>
            <p>Choose what you would like to practice.</p>
            <nav className="onboarding-steps" aria-label="Setup steps">
              {steps.map((label, index) => (
                <button
                  className={`onboarding-step${step === index ? " is-active" : ""}${index < step ? " is-done" : ""}`}
                  type="button"
                  key={label}
                  aria-current={step === index ? "step" : undefined}
                  onClick={() => goToStep(index)}
                  disabled={createProfile.isPending}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>{label}
                </button>
              ))}
            </nav>
            <div className="onboarding-side-note">You can edit your tutor preferences later. Learning progress and memories remain separate for each language profile.</div>
          </aside>

          <div className="onboarding-panel">
            {step === 0 ? (
              <section aria-labelledby="onboarding-heading">
                <p className="eyebrow">Step 1 of 4</p>
                <h2 id="onboarding-heading">Choose your languages</h2>
                <p className="onboarding-description">Which language should Mori use to help you, and which would you like to practice?</p>
                {catalog.isPending ? <p role="status">Loading available courses...</p> : null}
                {catalog.isError ? (
                  <div role="alert" className="onboarding-message">We could not load the course list. <button type="button" className="button" onClick={() => void catalog.refetch()}>Try again</button></div>
                ) : null}
                {catalog.isSuccess ? (
                  <>
                    <div className="onboarding-fields">
                      <label className="form-field"><span>Language for help</span><select aria-label="Language for help" value={base} onChange={(event) => { setBase(event.target.value); setTarget(""); changed(); }}><option value="">Choose a language</option>{baseLanguages.map(([id, name]) => <option value={id} key={id}>{name}</option>)}</select><small>Used for brief explanations when you get stuck.</small></label>
                      <label className="form-field"><span>Language to practice</span><select aria-label="Language to practice" value={target} disabled={!base} onChange={(event) => { setTarget(event.target.value); changed(); }}><option value="">Choose a language</option>{targets.map((pair) => <option value={pair.targetLanguageId} disabled={!pair.available} key={pair.targetLanguageId}>{pair.targetLanguageName} · {pair.targetNativeName}{pair.available ? "" : " - not available yet"}</option>)}</select><small>Only available courses can be selected.</small></label>
                    </div>
                    <div className="onboarding-availability"><strong>Course availability</strong><span>Courses shown as unavailable are still being prepared. Mori will only save a ready pair.</span></div>
                  </>
                ) : null}
              </section>
            ) : null}

            {step === 1 ? (
              <section aria-labelledby="onboarding-heading">
                <p className="eyebrow">Step 2 of 4</p>
                <h2 id="onboarding-heading">Where would you like to begin?</h2>
                <p className="onboarding-description">Pick the description that feels closest. This is a starting point, not a test result.</p>
                <div className="onboarding-choices" role="radiogroup" aria-label="Starting point">
                  {levelChoices.map((choice) => <label className={`onboarding-choice${startingChoice === choice.value ? " is-selected" : ""}`} key={choice.value}><input type="radio" name="starting-choice" value={choice.value} checked={startingChoice === choice.value} onChange={() => { setStartingChoice(choice.value); changed(); }} /><span><strong>{choice.title}</strong><small>{choice.description}</small></span></label>)}
                </div>
                <p className="onboarding-note">{startingChoice === "fluent" ? "Fluent is a practice mode. Mori will correct pronunciation only when you ask." : "This choice is provisional. If you're not sure, Mori begins at Beginner and uses later conversation evidence to assess your level."}</p>
              </section>
            ) : null}

            {step === 2 ? (
              <section aria-labelledby="onboarding-heading">
                <p className="eyebrow">Step 3 of 4</p>
                <h2 id="onboarding-heading">Set the conversation style</h2>
                <p className="onboarding-description">These preferences shape how Mori responds. You can edit them later.</p>
                <div className="onboarding-fields">
                  <label className="form-field"><span>Corrections</span><select aria-label="Corrections" value={corrections} disabled={startingChoice === "fluent"} onChange={(event) => { setCorrections(event.target.value as CorrectionPreference); changed(); }}><option value="balanced">Balanced - correct useful moments</option><option value="light">Light - keep the conversation flowing</option><option value="frequent">Frequent - correct more often</option></select><small>{startingChoice === "fluent" ? "In Fluent practice, Mori only corrects when asked." : "Mori still helps when an error blocks meaning."}</small></label>
                  <label className="form-field"><span>Tutor pace</span><select aria-label="Tutor pace" value={pace} onChange={(event) => { setPace(event.target.value as TutorPace); changed(); }}><option value="level">Adapt to my level - recommended</option><option value="gentle">Gentle</option><option value="steady">Steady</option><option value="natural">Natural</option></select><small>You can ask Mori to change pace during a session.</small></label>
                  <label className="form-field onboarding-wide"><span>Things you enjoy talking about (optional)</span><textarea aria-label="Things you enjoy talking about" value={interestsText} maxLength={1000} placeholder="For example: cooking, football, city walks" onChange={(event) => { setInterestsText(event.target.value); changed(); }} /><small>Separate interests with commas or new lines. Up to 12, with 80 characters each. Interests do not measure your ability.</small></label>
                </div>
                <p className="onboarding-note">Corrections and pace have suggested starting values. Your languages and starting point are always chosen by you.</p>
              </section>
            ) : null}

            {step === 3 ? (
              <section aria-labelledby="onboarding-heading">
                <p className="eyebrow">Step 4 of 4</p>
                <h2 id="onboarding-heading">Review your learning setup</h2>
                <p className="onboarding-description">Check your choices before Mori creates this language profile.</p>
                <dl className="onboarding-summary">
                  <div><dt>Language for help</dt><dd>{chosenPair?.baseLanguageName}</dd></div>
                  <div><dt>Language to practice</dt><dd>{chosenPair?.targetLanguageName} · {chosenPair?.targetNativeName}</dd></div>
                  <div><dt>Starting point</dt><dd>{levelChoices.find((choice) => choice.value === startingChoice)?.title}{startingChoice === "unsure" ? " - provisional Beginner" : startingChoice === "fluent" ? " - practice mode" : " - provisional"}</dd></div>
                  <div><dt>Corrections and pace</dt><dd>{startingChoice === "fluent" ? "Corrections when asked" : `${corrections} corrections`} · {pace === "level" ? "adapt to my level" : pace} pace</dd></div>
                  <div><dt>Interests</dt><dd>{parseInterests(interestsText).join(", ") || "None added"}</dd></div>
                </dl>
                <div className="onboarding-confirmation"><strong>What happens when you confirm</strong>Mori creates or confirms this language profile and takes you to the Study desk. A voice session starts only when you choose to practice.</div>
              </section>
            ) : null}

            {error ? <p className="onboarding-error" role="alert">{error}</p> : null}
            <div className="onboarding-actions"><button type="button" className="button onboarding-back" disabled={step === 0 || createProfile.isPending} onClick={() => { setError(""); setStep(step - 1); }}>Back</button><span>{step === 3 ? "No voice call starts yet." : "Your choices are saved when you confirm."}</span><button type="button" className="button button-primary" disabled={catalog.isPending || catalog.isError || createProfile.isPending} onClick={next}>{createProfile.isPending ? "Creating profile..." : step === 3 ? "Create my profile" : "Continue"}</button></div>
          </div>
        </div>
      </section>
    </main>
  );
}

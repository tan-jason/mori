import { Link } from "react-router-dom";
import { BrandMark } from "../../components/app-shell";

function GoogleMark() {
  return (
    <svg
      aria-hidden="true"
      className="google-mark"
      viewBox="0 0 24 24"
      width="20"
      height="20"
    >
      <path
        fill="#4285f4"
        d="M21.6 12.2c0-.7-.1-1.4-.2-2.1H12v4h5.4a4.7 4.7 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z"
      />
      <path
        fill="#34a853"
        d="M12 22c2.7 0 5-.9 6.7-2.3l-3.3-2.6c-.9.6-2.1 1-3.4 1a5.9 5.9 0 0 1-5.5-4.1H3.1v2.7A10 10 0 0 0 12 22Z"
      />
      <path
        fill="#fbbc05"
        d="M6.5 14a6 6 0 0 1 0-3.9V7.3H3.1a10 10 0 0 0 0 9.4L6.5 14Z"
      />
      <path
        fill="#ea4335"
        d="M12 5.9c1.5 0 2.8.5 3.9 1.5l2.9-2.9A9.8 9.8 0 0 0 3.1 7.3l3.4 2.8A5.9 5.9 0 0 1 12 5.9Z"
      />
    </svg>
  );
}

export function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-story" aria-labelledby="login-story-title">
        <Link className="login-brand brand" to="/login" aria-label="Mori sign in">
          <BrandMark />
          <span className="brand-copy">
            <strong>Mori</strong>
            <small>Conversation studio</small>
          </span>
        </Link>

        <div className="login-story-copy">
          <p className="eyebrow eyebrow-light">A conversation practice</p>
          <h1 id="login-story-title">Speak a little.<br />Remember more.</h1>
          <p>
            Natural speaking practice that meets you where you are and builds on
            every conversation.
          </p>
        </div>

        <div className="login-word-card" aria-hidden="true">
          <span className="login-word-index">Practice note</span>
          <strong>Take your time.</strong>
          <p>Progress grows one conversation at a time.</p>
        </div>

        <p className="login-story-note">Practice with patience · Speak with confidence</p>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel-inner">
          <div className="login-mobile-brand">
            <BrandMark />
            <span className="brand-copy">
              <strong>Mori</strong>
              <small>Conversation studio</small>
            </span>
          </div>

          <p className="eyebrow">Welcome to Mori</p>
          <h2 id="login-title">Your next conversation starts here.</h2>
          <p className="login-intro">
            Sign in to continue your language practice, learning history, and
            personalized sessions.
          </p>

          <Link className="google-button" to="/">
            <GoogleMark />
            Continue with Google
          </Link>

          <div className="login-assurance" role="note">
            <span aria-hidden="true">✓</span>
            <p>
              <strong>Your practice stays yours.</strong>
              We use your Google name and email for your account. Raw session audio
              is not saved by default.
            </p>
          </div>

          <p className="login-terms">
            By continuing, you confirm you are 18 or older and agree to the
            <a href="#terms"> Terms</a> and <a href="#privacy">Privacy Policy</a>.
          </p>
        </div>
      </section>
    </main>
  );
}

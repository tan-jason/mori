import { Link } from "react-router-dom";
import { PageErrorState, PageLoadingState } from "../../components/async-state";
import type { LearningState } from "../../domain/learning";
import { useDashboard } from "./use-dashboard";

const stateLabels: Record<LearningState, string> = {
  introduced: "Introduced",
  practiced: "Practicing",
  demonstrated: "Demonstrated",
  retained: "Retained",
};

export function DashboardPage() {
  const dashboard = useDashboard();

  if (dashboard.isPending) {
    return <PageLoadingState />;
  }

  if (dashboard.isError) {
    return <PageErrorState onRetry={() => void dashboard.refetch()} />;
  }

  const data = dashboard.data;
  const usagePercent =
    data.entitlement.sessionsIncluded > 0
      ? Math.min(
          100,
          Math.max(
            0,
            (data.entitlement.sessionsRemaining / data.entitlement.sessionsIncluded) *
              100,
          ),
        )
      : 0;

  return (
    <div className="dashboard-page">
      <section className="welcome-row" aria-labelledby="welcome-title">
        <div className="welcome-copy">
          <p className="eyebrow">Tuesday, September 1</p>
          <h1 id="welcome-title">Nǐ hǎo, {data.learner.displayName}.</h1>
          <p>Ready for a little Mandarin today?</p>
        </div>
        <div className="level-pill">
          <span className="level-pill-label">Course level</span>
          <strong>{data.learner.level}</strong>
          <small>Standard Mandarin · Active</small>
        </div>
      </section>

      <section className="session-hero" aria-labelledby="session-focus-title">
        <div className="session-hero-copy">
          <p className="eyebrow eyebrow-light">{data.suggestedFocus.eyebrow}</p>
          <h2 id="session-focus-title">{data.suggestedFocus.title}</h2>
          <p>{data.suggestedFocus.description}</p>
          <div className="session-meta" aria-label="Session details">
            <span>Up to 20 minutes</span>
            <span>Voice conversation</span>
          </div>
          <Link className="button button-light" to="/session">
            Start conversation
            <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="lesson-board" aria-hidden="true">
          <div className="lesson-board-heading">
            <span>Lesson 09</span>
            <strong>Today&apos;s word bank</strong>
          </div>
          <div className="lesson-words">
            <span>
              <strong>先</strong>
              xiān · first
            </span>
            <span>
              <strong>后来</strong>
              hòulái · later
            </span>
            <span>
              <strong>最后</strong>
              zuìhòu · finally
            </span>
          </div>
          <div className="lesson-prompt">
            <span>Conversation prompt</span>
            <p>“What did you do after work?”</p>
          </div>
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="card progress-card" aria-labelledby="progress-title">
          <span className="card-number" aria-hidden="true">
            01
          </span>
          <div className="card-heading">
            <div>
              <p className="eyebrow">This week</p>
              <h2 id="progress-title">Keep your rhythm</h2>
            </div>
            <span className="metric">
              {data.entitlement.sessionsRemaining}/{data.entitlement.sessionsIncluded}
            </span>
          </div>
          <p className="muted">
            {data.entitlement.sessionsRemaining} voice sessions available
          </p>
          <div
            className="progress-track"
            role="progressbar"
            aria-label="Weekly sessions remaining"
            aria-valuemin={0}
            aria-valuemax={data.entitlement.sessionsIncluded}
            aria-valuenow={data.entitlement.sessionsRemaining}
          >
            <span style={{ width: `${String(usagePercent)}%` }} />
          </div>
          <div className="split-meta">
            <span>{data.entitlement.label}</span>
            <span>{data.entitlement.resetLabel}</span>
          </div>
        </section>

        <section className="card review-card" aria-labelledby="review-title">
          <span className="card-number" aria-hidden="true">
            02
          </span>
          <div className="review-number">{data.dueReviewCount}</div>
          <div>
            <p className="eyebrow">Ready to revisit</p>
            <h2 id="review-title">Quick reviews due</h2>
            <p className="muted">
              These will naturally return in an upcoming conversation.
            </p>
          </div>
        </section>
      </div>

      <section className="section-block" aria-labelledby="learning-title">
        <div className="section-heading">
          <span className="section-number" aria-hidden="true">
            01
          </span>
          <div>
            <p className="eyebrow">Growing vocabulary</p>
            <h2 id="learning-title">Recent learning</h2>
          </div>
          <span className="text-link">Progress is evidence-based</span>
        </div>
        <div className="learning-grid">
          {data.recentItems.map((item) => (
            <article className="learning-card" key={item.id}>
              <div className="hanzi-large">{item.hanzi}</div>
              <div>
                <p className="pinyin">{item.pinyin}</p>
                <p>{item.meaning}</p>
              </div>
              <span className={`state-badge state-${item.state}`}>
                {stateLabels[item.state]}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block" aria-labelledby="sessions-title">
        <div className="section-heading">
          <span className="section-number" aria-hidden="true">
            02
          </span>
          <div>
            <p className="eyebrow">Your conversations</p>
            <h2 id="sessions-title">Recent sessions</h2>
          </div>
        </div>
        <div className="session-list">
          <div className="session-list-heading" aria-hidden="true">
            <span>Lesson</span>
            <span>Conversation record</span>
            <span>Status</span>
            <span />
          </div>
          {data.recentSessions.map((session) => (
            <Link className="session-row" to={`/recaps/${session.id}`} key={session.id}>
              <span className="session-index" aria-hidden="true">
                语
              </span>
              <span className="session-row-title">
                <strong>{session.title}</strong>
                <span>
                  {session.completedAtLabel} · {session.durationMinutes} min
                </span>
              </span>
              <span className="session-status">
                {session.status === "ready" ? "View recap" : "Processing"}
              </span>
              <span aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      </section>

      <aside className="practice-note">
        <span className="practice-note-label">Tutor note</span>
        <span className="practice-note-mark" aria-hidden="true">
          木
        </span>
        <p>
          <strong>Speak with what you have.</strong> If a word is missing, describe it
          in Mandarin. Your tutor will help without judgment.
        </p>
      </aside>
    </div>
  );
}

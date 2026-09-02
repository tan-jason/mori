import { Link, useParams } from "react-router-dom";
import { PageErrorState, PageLoadingState } from "../../components/async-state";
import { useRecap } from "./use-recap";

export function RecapPage() {
  const { sessionId } = useParams();
  const recap = useRecap(sessionId ?? "unknown");

  if (recap.isPending) {
    return <PageLoadingState />;
  }

  if (recap.isError) {
    return <PageErrorState onRetry={() => void recap.refetch()} />;
  }

  const data = recap.data;

  return (
    <div className="detail-page recap-page">
      <Link className="back-link" to="/">
        <span aria-hidden="true">←</span> Back to home
      </Link>

      <header className="detail-hero">
        <p className="eyebrow">Session recap</p>
        <h1>{data.title}</h1>
        <p className="detail-meta">
          {data.completedAtLabel} · {data.durationMinutes} minutes
        </p>
        <p className="detail-summary">{data.summary}</p>
      </header>

      <div className="detail-grid">
        <section className="card" aria-labelledby="objectives-title">
          <p className="eyebrow">Practice plan</p>
          <h2 id="objectives-title">Your objectives</h2>
          <ul className="objective-list">
            {data.objectives.map((objective) => (
              <li key={objective.label}>
                <span className={`objective-mark objective-${objective.outcome}`}>
                  {objective.outcome === "demonstrated" ? "✓" : "○"}
                </span>
                <span>
                  <strong>{objective.label}</strong>
                  <small>
                    {objective.outcome === "demonstrated"
                      ? "Demonstrated in conversation"
                      : "Attempted with support"}
                  </small>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card next-focus-card" aria-labelledby="next-focus-title">
          <p className="eyebrow">Looking ahead</p>
          <h2 id="next-focus-title">Next session</h2>
          <p>{data.nextFocus}</p>
          <Link className="text-link" to="/session">
            Prepare another conversation →
          </Link>
        </section>
      </div>

      <section className="section-block" aria-labelledby="corrections-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Worth noticing</p>
            <h2 id="corrections-title">A useful correction</h2>
          </div>
        </div>
        {data.corrections.map((correction) => (
          <article className="correction-card" key={correction.after}>
            <div>
              <span>Your version</span>
              <p>{correction.before}</p>
            </div>
            <div>
              <span>A more natural version</span>
              <p>{correction.after}</p>
            </div>
            <p className="correction-note">{correction.explanation}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

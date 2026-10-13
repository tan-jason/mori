import { Link, useParams } from "react-router-dom";
import { PageErrorState, PageLoadingState } from "../../components/async-state";
import { useRecap } from "./use-recap";

export function RecapPage() {
  const { sessionId } = useParams();
  const recap = useRecap(sessionId ?? "unknown");

  if (recap.isPending) return <PageLoadingState />;
  if (recap.isError) return <PageErrorState onRetry={() => void recap.refetch()} />;

  const data = recap.data;
  const ready = data.status === "ready";

  return (
    <div className="detail-page recap-page">
      <Link className="back-link" to="/">
        <span aria-hidden="true">←</span> Back to home
      </Link>

      <header className="detail-hero">
        <p className="eyebrow">Session recap</p>
        <h1>{ready ? "Your conversation" : data.status === "processing" ? "Putting your recap together" : "Recap unavailable"}</h1>
        <p className="detail-summary" role="status">
          {ready ? data.summary : data.status === "processing"
            ? "Your conversation has ended. Mori is preparing a short recap."
            : "We could not prepare a reliable recap from this conversation."}
        </p>
      </header>

      {ready && data.mode === "learning" && (
        <>
          <section className="section-block" aria-labelledby="observations-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">From your conversation</p>
                <h2 id="observations-title">Things you practiced</h2>
              </div>
            </div>
            {data.observations?.length ? (
              <ul className="objective-list">
                {data.observations.map((observation, index) => (
                  <li key={`${observation.kind}-${index}`}>
                    <span className="objective-mark objective-attempted" aria-hidden="true">○</span>
                    <span>{observation.detail}</span>
                  </li>
                ))}
              </ul>
            ) : <p>There was not enough clear conversation to highlight a specific practice moment.</p>}
          </section>

          {Boolean(data.corrections?.length) && (
            <section className="section-block" aria-labelledby="corrections-title">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Worth noticing</p>
                  <h2 id="corrections-title">A useful way to say it</h2>
                </div>
              </div>
              {data.corrections?.map((correction) => (
                <article className="correction-card" key={correction.learnerTurnId}>
                  <div><span>Your version</span><p>{correction.before}</p></div>
                  <div><span>Another way</span><p>{correction.suggestion}</p></div>
                </article>
              ))}
            </section>
          )}
        </>
      )}

      <Link className="text-link" to="/session">Prepare another conversation →</Link>
    </div>
  );
}

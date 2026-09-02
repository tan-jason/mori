import { PageErrorState, PageLoadingState } from "../../components/async-state";
import { useMemories } from "./use-memories";

export function MemoriesPage() {
  const memories = useMemories();

  if (memories.isPending) {
    return <PageLoadingState />;
  }

  if (memories.isError) {
    return <PageErrorState onRetry={() => void memories.refetch()} />;
  }

  return (
    <div className="detail-page memories-page">
      <header className="detail-hero detail-hero-compact">
        <p className="eyebrow">Privacy and personalization</p>
        <h1>Your remembered information</h1>
        <p className="detail-summary">
          Mori keeps learning progress separate from optional conversation memories.
          You will be able to remove any memory without changing what you have learned.
        </p>
      </header>

      <section className="section-block" aria-labelledby="memories-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Conversation context</p>
            <h2 id="memories-title">Current memories</h2>
          </div>
          <span className="count-pill">{memories.data.length}</span>
        </div>
        <div className="memory-list">
          {memories.data.map((memory) => (
            <article className="memory-card" key={memory.id}>
              <div className="memory-mark" aria-hidden="true">
                记
              </div>
              <div>
                <h3>{memory.label}</h3>
                <p>{memory.detail}</p>
                <p className="memory-source">
                  {memory.sourceLabel} · {memory.expiresLabel}
                </p>
              </div>
              <button
                className="button button-danger-quiet"
                type="button"
                disabled
                title="Backend mutation is not implemented"
              >
                Delete
              </button>
            </article>
          ))}
        </div>
      </section>

      <aside className="privacy-note">
        <strong>Designed for data minimization</strong>
        <p>
          Sensitive details are not proactively retained or resurfaced. Raw audio is
          not retained by default.
        </p>
      </aside>
    </div>
  );
}

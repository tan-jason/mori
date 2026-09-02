interface AsyncStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function PageLoadingState() {
  return (
    <div className="loading-stack" aria-label="Loading" role="status">
      <span className="skeleton skeleton-title" />
      <span className="skeleton skeleton-card" />
      <span className="skeleton skeleton-card skeleton-card-short" />
    </div>
  );
}

export function PageErrorState({
  title = "Something went quiet",
  message = "We could not load this page. Please try again.",
  onRetry,
}: AsyncStateProps) {
  return (
    <section className="empty-state" role="alert">
      <p className="eyebrow">Connection issue</p>
      <h1>{title}</h1>
      <p>{message}</p>
      {onRetry ? (
        <button className="button button-primary" type="button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </section>
  );
}

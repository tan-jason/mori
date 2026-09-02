import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

export function RouteErrorPage() {
  const error = useRouteError();
  const isNotFound = isRouteErrorResponse(error) && error.status === 404;

  return (
    <main className="standalone-error">
      <p className="eyebrow">{isNotFound ? "404" : "Unexpected error"}</p>
      <h1>{isNotFound ? "This page wandered off." : "Mori needs a moment."}</h1>
      <p>
        {isNotFound
          ? "The page you requested does not exist."
          : "The application hit an unexpected problem."}
      </p>
      <Link className="button button-primary" to="/">
        Return home
      </Link>
    </main>
  );
}

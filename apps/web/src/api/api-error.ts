export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ApiError";
  }
}

export function isAuthenticationRequired(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 401 || error.code === "authentication_required")
  );
}

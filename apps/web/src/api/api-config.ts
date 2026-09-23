const DEFAULT_API_ORIGIN = "http://localhost:8000";

export function getApiOrigin(): string {
  const configuredOrigin = import.meta.env.VITE_API_ORIGIN?.trim();
  const candidate = configuredOrigin || DEFAULT_API_ORIGIN;

  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      throw new Error("VITE_API_ORIGIN must use HTTP or HTTPS.");
    }
    if (url.pathname !== "/" || url.search || url.hash) {
      throw new Error("VITE_API_ORIGIN must contain only an origin.");
    }
    return url.origin;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("VITE_API_ORIGIN")) {
      throw error;
    }
    throw new Error("VITE_API_ORIGIN must be an absolute HTTP or HTTPS origin.", {
      cause: error,
    });
  }
}

export function getGoogleSignInUrl(returnTo = "/"): string {
  const url = new URL("/auth/google/start", getApiOrigin());
  url.searchParams.set("return_to", returnTo);
  return url.toString();
}

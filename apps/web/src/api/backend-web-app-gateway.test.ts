import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api-error";
import { createBackendWebAppGateway } from "./backend-web-app-gateway";

const learnerResponse = {
  user: {
    id: "b25fdaa6-4362-4c47-851a-ad667118c0ac",
    email: "learner@example.com",
    displayName: "Mori Learner",
    status: "active",
  },
  onboarding: { complete: false },
  activeLanguageProfile: {
    id: "61a971ee-4cd7-465c-a9f9-1cbfc4342cd4",
    baseLanguageId: "english",
    targetLanguageId: "mandarin",
    status: "active",
  },
  preferences: {
    correctionPreference: "balanced",
    tutorPace: "level",
    captionsEnabled: false,
    timezone: "America/New_York",
    version: 1,
  },
  csrfToken: "csrf-token",
} as const;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("createBackendWebAppGateway", () => {
  it("restores the learner session with credentials and validates the response", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(jsonResponse(learnerResponse));
    const gateway = createBackendWebAppGateway({
      apiOrigin: "http://api.test",
      fetch: fetchMock,
    });

    await expect(gateway.getCurrentLearner()).resolves.toMatchObject({
      user: { displayName: "Mori Learner" },
      activeLanguageProfile: { targetLanguageId: "mandarin" },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      new URL("http://api.test/api/v1/me"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("sends the CSRF token and preference version when saving", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(
      jsonResponse({
        ...learnerResponse,
        preferences: {
          ...learnerResponse.preferences,
          correctionPreference: "frequent",
          version: 2,
        },
      }),
    );
    const gateway = createBackendWebAppGateway({
      apiOrigin: "http://api.test",
      fetch: fetchMock,
    });

    const learner = await gateway.updatePreferences({
      changes: {
        correctionPreference: "frequent",
        tutorPace: "level",
        timezone: "America/New_York",
      },
      csrfToken: "csrf-token",
      expectedVersion: 1,
    });

    expect(learner.preferences.version).toBe(2);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toEqual(new URL("http://api.test/api/v1/me/preferences"));
    expect(init).toMatchObject({
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "If-Match": '"1"',
        "X-CSRF-Token": "csrf-token",
      },
    });
    expect(init?.body).toBe(
      JSON.stringify({
        correctionPreference: "frequent",
        tutorPace: "level",
        timezone: "America/New_York",
      }),
    );
  });

  it("preserves the backend authentication error for the route guard", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "authentication_required",
            message: "Authentication is required.",
            requestId: "request-1",
          },
        },
        401,
      ),
    );
    const gateway = createBackendWebAppGateway({
      apiOrigin: "http://api.test",
      fetch: fetchMock,
    });

    await expect(gateway.getCurrentLearner()).rejects.toEqual(
      new ApiError(
        401,
        "authentication_required",
        "Authentication is required.",
        "request-1",
      ),
    );
  });

  it("rejects malformed learner payloads at the transport boundary", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(
      jsonResponse({ ...learnerResponse, csrfToken: undefined }),
    );
    const gateway = createBackendWebAppGateway({
      apiOrigin: "http://api.test",
      fetch: fetchMock,
    });

    await expect(gateway.getCurrentLearner()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });

  it("rejects a non-JSON learner response at the transport boundary", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(new Response("not-json"));
    const gateway = createBackendWebAppGateway({
      apiOrigin: "http://api.test",
      fetch: fetchMock,
    });

    await expect(gateway.getCurrentLearner()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
});

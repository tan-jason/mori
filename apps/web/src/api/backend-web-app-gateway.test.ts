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
  version: 2,
  onboarding: { complete: true },
  activeLanguageProfile: {
    id: "61a971ee-4cd7-465c-a9f9-1cbfc4342cd4",
    baseLanguageId: "english",
    targetLanguageId: "mandarin",
    status: "active",
    languageSelectionConfirmed: true,
    version: 1,
    learning: {
      mode: "learning",
      startingChoice: "beginner",
      provisionalLevel: "beginner",
      version: 1,
    },
  },
  preferences: {
    correctionPreference: "balanced",
    tutorPace: "level",
    captionsEnabled: false,
    timezone: "America/New_York",
    interests: [],
    learningGoal: "Talk with family",
    speakingContext: "Casual conversations with relatives",
    learningNotes: "",
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
  it("reads and manages captured learner-file entries with CSRF and versions", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    const entry = {
      id: "7ed83ec5-7f63-416c-aedb-cf30b9224170",
      kind: "insight", text: "Interested in food.", origin: "capture", version: 1,
      sourceSessionId: "f89df529-19ce-4022-9653-06f2adeb5e0c",
      createdAt: "2026-10-07T12:00:00Z", updatedAt: "2026-10-07T12:00:00Z",
      expiresAt: "2027-01-05T12:00:00Z",
    };
    fetchMock.mockResolvedValueOnce(jsonResponse({ entries: [entry], nextCursor: null }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...entry, text: "Interested in cooking.", origin: "learner_edit", version: 2 }));
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const gateway = createBackendWebAppGateway({ apiOrigin: "http://api.test", fetch: fetchMock });
    const profileId = learnerResponse.activeLanguageProfile.id;
    await expect(gateway.getLearnerFile(profileId)).resolves.toMatchObject({ entries: [entry] });
    await expect(gateway.editLearnerFileEntry({ languageProfileId: profileId, entryId: entry.id,
      expectedVersion: 1, text: "Interested in cooking.", csrfToken: "csrf-token" }))
      .resolves.toMatchObject({ version: 2 });
    await gateway.deleteLearnerFileEntry({ languageProfileId: profileId, entryId: entry.id,
      expectedVersion: 2, csrfToken: "csrf-token" });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "PATCH", headers: {
      "If-Match": '"1"', "X-CSRF-Token": "csrf-token",
    } });
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: "DELETE", headers: {
      "If-Match": '"2"', "X-CSRF-Token": "csrf-token",
    } });
  });

  it("reads a validated recap instead of preview content", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(jsonResponse({
      mode: "learning",
      status: "ready",
      summary: "You practiced an introduction.",
      observations: [{ kind: "use", detail: "You described your day.", learnerTurnIds: ["61a971ee-4cd7-465c-a9f9-1cbfc4342cd4"] }],
      corrections: [],
    }));
    const gateway = createBackendWebAppGateway({ apiOrigin: "http://api.test", fetch: fetchMock });
    await expect(gateway.getRecap("session-123", learnerResponse.activeLanguageProfile.id)).resolves.toMatchObject({
      id: "session-123",
      status: "ready",
      observations: [{ detail: "You described your day." }],
    });
    expect(fetchMock.mock.calls[0]?.[0]).toEqual(new URL("http://api.test/api/v1/sessions/session-123/recap"));
  });

  it("creates a session with the selected profile and validates the saved plan", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    const session = {
      id: "a92983a7-1476-47d9-b6f0-39d8c2d9ebf1",
      state: "planned",
      rowVersion: 3,
      connectedLimitMs: 1_200_000,
      connectedMs: 0,
      reservationExpiresAt: "2026-09-30T12:10:00Z",
      objective: "Share a simple introduction.",
      planPreview: { objectives: ["Share a simple introduction."] },
      mode: "learning",
      createdAt: "2026-09-30T12:00:00Z",
    };
    fetchMock.mockResolvedValue(jsonResponse(session, 201));
    const gateway = createBackendWebAppGateway({ apiOrigin: "http://api.test", fetch: fetchMock });

    await expect(gateway.createSession({
      languageProfileId: learnerResponse.activeLanguageProfile.id,
      topic: "my weekend",
      requestedWords: ["market"],
      idempotencyKey: "session-setup-123",
      csrfToken: "csrf-token",
    })).resolves.toMatchObject({ id: session.id, planPreview: session.planPreview });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toEqual(new URL("http://api.test/api/v1/sessions"));
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "session-setup-123",
        "X-CSRF-Token": "csrf-token",
      },
    });
    expect(JSON.parse(init?.body as string)).toEqual({
      languageProfileId: learnerResponse.activeLanguageProfile.id,
      topic: "my weekend",
      requestedWords: ["market"],
    });
  });

  it("accepts a signed-in learner before profile setup", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(jsonResponse({
      ...learnerResponse,
      version: 1,
      onboarding: { complete: false },
      activeLanguageProfile: null,
      preferences: null,
    }));
    const gateway = createBackendWebAppGateway({ apiOrigin: "http://api.test", fetch: fetchMock });
    await expect(gateway.getCurrentLearner()).resolves.toMatchObject({
      onboarding: { complete: false }, activeLanguageProfile: null, preferences: null,
    });
  });

  it("sends explicit choices with an idempotency key", async () => {
    const fetchMock = vi.fn<typeof window.fetch>();
    fetchMock.mockResolvedValue(jsonResponse({ pairs: [{
      baseLanguageId: "english", targetLanguageId: "mandarin",
      baseLanguageName: "English", targetLanguageName: "Mandarin",
      targetNativeName: "中文", available: true,
    }] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ pairs: [{
      baseLanguageId: "english", targetLanguageId: "mandarin",
      baseLanguageName: "English", targetLanguageName: "Mandarin",
      targetNativeName: "中文", available: true,
    }] }));
    fetchMock.mockResolvedValueOnce(jsonResponse(learnerResponse, 201));
    const gateway = createBackendWebAppGateway({ apiOrigin: "http://api.test", fetch: fetchMock });
    await gateway.getLanguagePairs();
    await gateway.createLanguageProfile({
      baseLanguageId: "english", targetLanguageId: "mandarin", startingChoice: "unsure",
      correctionPreference: "balanced", tutorPace: "level", timezone: "UTC",
      interests: ["Cooking"], idempotencyKey: "profile-setup-123", csrfToken: "csrf-token",
      learningGoal: "Talk with family", speakingContext: "Casual conversations with relatives",
      learningNotes: "",
    });
    const [url, init] = fetchMock.mock.calls[1] ?? [];
    expect(url).toEqual(new URL("http://api.test/api/v1/language-profiles"));
    expect(init).toMatchObject({
      method: "POST",
      headers: {
        "Idempotency-Key": "profile-setup-123", "X-CSRF-Token": "csrf-token",
      },
    });
    expect(typeof init?.body).toBe("string");
    expect(JSON.parse(init?.body as string)).toMatchObject({
      baseLanguageId: "english", targetLanguageId: "mandarin", startingChoice: "unsure",
      learningGoal: "Talk with family",
      speakingContext: "Casual conversations with relatives",
    });
  });
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
        learningGoal: "Talk with family",
        speakingContext: "Casual conversations with relatives",
        learningNotes: "",
      },
      csrfToken: "csrf-token",
      expectedVersion: 1,
    });

    expect(learner.preferences?.version).toBe(2);
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
        learningGoal: "Talk with family",
        speakingContext: "Casual conversations with relatives",
        learningNotes: "",
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

import { zApiErrorResponse, zGetRecapApiV1SessionsSessionIdRecapGetResponse, zLanguagePairsResponse, zLearnerFileEntryResponse, zLearnerFileResponse, zMeResponse, zSessionResponse, zVoiceAvailabilityResponse } from "@mori/api-client/zod";
import type { CurrentLearner } from "../domain/identity";
import { isTargetLanguageId, type TargetLanguageId } from "../domain/languages";
import { getApiOrigin } from "./api-config";
import { ApiError } from "./api-error";
import { createMockWebAppGateway } from "./mock-web-app-gateway";
import type { WebAppGateway } from "./web-app-gateway";

interface BackendWebAppGatewayOptions {
  apiOrigin?: string;
  fetch?: typeof window.fetch;
}

async function readError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new ApiError(
      response.status,
      "unexpected_response",
      "Mori returned an unexpected response.",
    );
  }

  const parsed = zApiErrorResponse.safeParse(payload);
  if (!parsed.success) {
    return new ApiError(
      response.status,
      "unexpected_response",
      "Mori returned an unexpected response.",
    );
  }

  return new ApiError(
    response.status,
    parsed.data.error.code,
    parsed.data.error.message,
    parsed.data.error.requestId,
  );
}

export function createBackendWebAppGateway(
  options: BackendWebAppGatewayOptions = {},
): WebAppGateway {
  const apiOrigin = options.apiOrigin ?? getApiOrigin();
  const fetchImplementation = options.fetch ?? window.fetch.bind(window);
  const previewGateway = createMockWebAppGateway();
  const previewLanguageProfileId = "english-mandarin";

  const request = async (
    path: string,
    init: RequestInit = {},
  ): Promise<Response> => {
    try {
      const response = await fetchImplementation(new URL(path, apiOrigin), {
        ...init,
        cache: "no-store",
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...init.headers,
        },
      });
      if (!response.ok) {
        throw await readError(response);
      }
      return response;
    } catch (error) {
      if (error instanceof ApiError || error instanceof DOMException) {
        throw error;
      }
      throw new ApiError(
        0,
        "network_error",
        "Mori could not be reached.",
        undefined,
        { cause: error },
      );
    }
  };

  const readCurrentLearner = async (
    response: Response,
  ): Promise<CurrentLearner> => {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch (error) {
      throw new ApiError(
        response.status,
        "invalid_response",
        "Mori returned an invalid learner profile.",
        response.headers.get("X-Request-ID") ?? undefined,
        { cause: error },
      );
    }
    const parsed = zMeResponse.safeParse(payload);
    if (
      !parsed.success ||
      (parsed.data.activeLanguageProfile !== null &&
        (parsed.data.activeLanguageProfile.baseLanguageId !== "english" ||
          !isTargetLanguageId(parsed.data.activeLanguageProfile.targetLanguageId))) ||
      (parsed.data.onboarding.complete &&
        (parsed.data.activeLanguageProfile === null || parsed.data.preferences === null))
    ) {
      throw new ApiError(
        response.status,
        "invalid_response",
        "Mori returned an invalid learner profile.",
        response.headers.get("X-Request-ID") ?? undefined,
        { cause: parsed.success ? undefined : parsed.error },
      );
    }
    return {
      ...parsed.data,
      activeLanguageProfile: parsed.data.activeLanguageProfile === null
        ? null
        : {
            ...parsed.data.activeLanguageProfile,
            baseLanguageId: "english",
            targetLanguageId: parsed.data.activeLanguageProfile.targetLanguageId as TargetLanguageId,
          },
    };
  };

  return {
    async getCurrentLearner(signal) {
      const response = await request("/api/v1/me", { signal });
      return readCurrentLearner(response);
    },

    async getLanguagePairs(signal) {
      const response = await request("/api/v1/language-pairs", { signal });
      const payload: unknown = await response.json();
      const parsed = zLanguagePairsResponse.safeParse(payload);
      if (!parsed.success) {
        throw new ApiError(response.status, "invalid_response", "Mori returned an invalid course list.");
      }
      return parsed.data.pairs;
    },

    async createLanguageProfile(command, signal) {
      const response = await request("/api/v1/language-profiles", {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": command.idempotencyKey,
          "X-CSRF-Token": command.csrfToken,
        },
        body: JSON.stringify({
          baseLanguageId: command.baseLanguageId,
          targetLanguageId: command.targetLanguageId,
          startingChoice: command.startingChoice,
          correctionPreference: command.correctionPreference,
          tutorPace: command.tutorPace,
          timezone: command.timezone,
          interests: command.interests,
          learningGoal: command.learningGoal,
          speakingContext: command.speakingContext,
          learningNotes: command.learningNotes,
        }),
      });
      return readCurrentLearner(response);
    },

    async updatePreferences(command, signal) {
      const response = await request("/api/v1/me/preferences", {
        method: "PATCH",
        signal,
        headers: {
          "Content-Type": "application/json",
          "If-Match": `"${String(command.expectedVersion)}"`,
          "X-CSRF-Token": command.csrfToken,
        },
        body: JSON.stringify(command.changes),
      });
      return readCurrentLearner(response);
    },

    async logout(csrfToken, signal) {
      await request("/auth/logout", {
        method: "POST",
        signal,
        headers: {
          "X-CSRF-Token": csrfToken,
        },
      });
    },

    async createSession(command, signal) {
      const response = await request("/api/v1/sessions", {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": command.idempotencyKey,
          "X-CSRF-Token": command.csrfToken,
        },
        body: JSON.stringify({
          languageProfileId: command.languageProfileId,
          topic: command.topic,
          requestedWords: command.requestedWords,
        }),
      });
      const payload: unknown = await response.json();
      const parsed = zSessionResponse.safeParse(payload);
      if (!parsed.success) {
        throw new ApiError(response.status, "invalid_response", "Mori returned an invalid session.");
      }
      return parsed.data;
    },

    async getSession(sessionId, signal) {
      const response = await request(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, { signal });
      const payload: unknown = await response.json();
      const parsed = zSessionResponse.safeParse(payload);
      if (!parsed.success) {
        throw new ApiError(response.status, "invalid_response", "Mori returned an invalid session.");
      }
      return parsed.data;
    },

    async getVoiceAvailability(signal) {
      const response = await request("/api/v1/sessions/availability", { signal });
      const payload: unknown = await response.json();
      const parsed = zVoiceAvailabilityResponse.safeParse(payload);
      if (!parsed.success) {
        throw new ApiError(response.status, "invalid_response", "Mori returned invalid voice availability.");
      }
      return parsed.data;
    },

    // Identity is live first. Learning read models remain deterministic previews
    // until their API endpoints are delivered in the next backend slice.
    getDashboard(_languageProfileId, signal) {
      return previewGateway.getDashboard(previewLanguageProfileId, signal);
    },

    async getRecap(sessionId, _languageProfileId, signal) {
      const response = await request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/recap`, { signal });
      const payload: unknown = await response.json();
      const parsed = zGetRecapApiV1SessionsSessionIdRecapGetResponse.safeParse(payload);
      if (!parsed.success) {
        throw new ApiError(response.status, "invalid_response", "Mori returned an invalid recap.");
      }
      if (parsed.data.mode === "practice") {
        return { id: sessionId, mode: "practice", status: parsed.data.status, summary: parsed.data.summary ?? undefined };
      }
      return {
        id: sessionId,
        mode: "learning",
        status: parsed.data.status,
        summary: parsed.data.summary ?? undefined,
        observations: parsed.data.observations ?? undefined,
        corrections: parsed.data.corrections ?? undefined,
      };
    },

    async getLearnerFile(languageProfileId, cursor, signal) {
      const path = `/api/v1/language-profiles/${encodeURIComponent(languageProfileId)}/learner-file`;
      const response = await request(cursor ? `${path}?cursor=${encodeURIComponent(cursor)}` : path, { signal });
      const parsed = zLearnerFileResponse.safeParse(await response.json());
      if (!parsed.success) throw new ApiError(response.status, "invalid_response", "Mori returned an invalid learner file.");
      return parsed.data;
    },

    async editLearnerFileEntry(command, signal) {
      const response = await request(`/api/v1/language-profiles/${encodeURIComponent(command.languageProfileId)}/learner-file/${encodeURIComponent(command.entryId)}`, {
        method: "PATCH", signal,
        headers: { "Content-Type": "application/json", "If-Match": `"${command.expectedVersion}"`, "X-CSRF-Token": command.csrfToken },
        body: JSON.stringify({ text: command.text }),
      });
      const parsed = zLearnerFileEntryResponse.safeParse(await response.json());
      if (!parsed.success) throw new ApiError(response.status, "invalid_response", "Mori returned an invalid learner file entry.");
      return parsed.data;
    },

    async deleteLearnerFileEntry(command, signal) {
      await request(`/api/v1/language-profiles/${encodeURIComponent(command.languageProfileId)}/learner-file/${encodeURIComponent(command.entryId)}`, {
        method: "DELETE", signal,
        headers: { "If-Match": `"${command.expectedVersion}"`, "X-CSRF-Token": command.csrfToken },
      });
    },
  };
}

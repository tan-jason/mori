import { z } from "zod";
import type { CurrentLearner } from "../domain/identity";
import { isTargetLanguageId } from "../domain/languages";
import { getApiOrigin } from "./api-config";
import { ApiError } from "./api-error";
import { createMockWebAppGateway } from "./mock-web-app-gateway";
import type { WebAppGateway } from "./web-app-gateway";

const apiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string(),
        requestId: z.string().optional(),
      })
      .strict(),
  })
  .strict();

const targetLanguageIdSchema = z.string().refine(isTargetLanguageId, {
  message: "Unsupported target language",
});

const currentLearnerSchema = z
  .object({
    user: z
      .object({
        id: z.string().uuid(),
        email: z.email(),
        displayName: z.string().min(1),
        status: z.enum(["active", "suspended", "deletion_pending"]),
      })
      .strict(),
    onboarding: z.object({ complete: z.boolean() }).strict(),
    activeLanguageProfile: z
      .object({
        id: z.string().uuid(),
        baseLanguageId: z.literal("english"),
        targetLanguageId: targetLanguageIdSchema,
        status: z.enum(["active", "archived"]),
      })
      .strict(),
    preferences: z
      .object({
        correctionPreference: z.enum(["light", "balanced", "frequent"]),
        tutorPace: z.enum(["level", "gentle", "steady", "natural"]),
        captionsEnabled: z.boolean(),
        timezone: z.string().min(1),
        version: z.number().int().positive(),
      })
      .strict(),
    csrfToken: z.string().min(1),
  })
  .strict();

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

  const parsed = apiErrorSchema.safeParse(payload);
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
    const parsed = currentLearnerSchema.safeParse(payload);
    if (!parsed.success) {
      throw new ApiError(
        response.status,
        "invalid_response",
        "Mori returned an invalid learner profile.",
        response.headers.get("X-Request-ID") ?? undefined,
        { cause: parsed.error },
      );
    }
    return parsed.data;
  };

  return {
    async getCurrentLearner(signal) {
      const response = await request("/api/v1/me", { signal });
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

    // Identity is live first. Learning read models remain deterministic previews
    // until their API endpoints are delivered in the next backend slice.
    getDashboard(_languageProfileId, signal) {
      return previewGateway.getDashboard(previewLanguageProfileId, signal);
    },

    getRecap(sessionId, _languageProfileId, signal) {
      return previewGateway.getRecap(
        sessionId,
        previewLanguageProfileId,
        signal,
      );
    },

    getMemories(_languageProfileId, signal) {
      return previewGateway.getMemories(previewLanguageProfileId, signal);
    },
  };
}

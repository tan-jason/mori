import { zApiErrorResponse } from "@mori/api-client/zod";
import { ApiError } from "../api/api-error";
import { getApiOrigin } from "../api/api-config";
import type { BrowserRealtimeTransport } from "./browser-realtime-session";

interface Options {
  apiOrigin?: string;
  fetch?: typeof window.fetch;
}

export function createBackendRealtimeTransport(options: Options = {}): BrowserRealtimeTransport {
  const origin = options.apiOrigin ?? getApiOrigin();
  const fetchImplementation = options.fetch ?? window.fetch.bind(window);

  const request = async (path: string, init: RequestInit): Promise<Response> => {
    let response: Response;
    try {
      response = await fetchImplementation(new URL(path, origin), {
        ...init,
        credentials: "include",
        cache: "no-store",
      });
    } catch (error) {
      throw new ApiError(0, "network_error", "Mori could not be reached.", undefined, { cause: error });
    }
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      const parsed = zApiErrorResponse.safeParse(payload);
      throw new ApiError(
        response.status,
        parsed.success ? parsed.data.error.code : "unexpected_response",
        parsed.success ? parsed.data.error.message : "Mori could not start the voice connection.",
        parsed.success ? parsed.data.error.requestId : undefined,
      );
    }
    return response;
  };

  return {
    async exchangeSdp(sessionId, csrfToken, offerSdp) {
      const response = await request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/webrtc`, {
        method: "POST",
        headers: { "Content-Type": "application/sdp", "X-CSRF-Token": csrfToken },
        body: offerSdp,
      });
      const answerSdp = await response.text();
      const attemptId = response.headers.get("X-Call-Attempt-ID");
      const deadlineAt = response.headers.get("X-Call-Deadline-At");
      if (!answerSdp || !attemptId || !deadlineAt || !Number.isFinite(Date.parse(deadlineAt))) {
        throw new ApiError(response.status, "invalid_response", "Mori returned an invalid voice connection.");
      }
      return { answerSdp, attemptId, deadlineAt };
    },

    async acknowledge(sessionId, attemptId, csrfToken) {
      await request(
        `/api/v1/sessions/${encodeURIComponent(sessionId)}/connections/${encodeURIComponent(attemptId)}/ack`,
        { method: "POST", headers: { "X-CSRF-Token": csrfToken } },
      );
    },

    async requestEnd(sessionId, csrfToken) {
      await request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/end`, {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken },
      });
    },
  };
}

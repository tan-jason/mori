import type { SessionResponse } from "@mori/api-client";

export type PlannedSession = SessionResponse;

export interface CreateSessionCommand {
  languageProfileId: string;
  topic: string | null;
  requestedWords: string[];
  idempotencyKey: string;
  csrfToken: string;
}

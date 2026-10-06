import type { WebAppGateway } from "./web-app-gateway";
import type { CurrentLearner, LanguagePair } from "../domain/identity";
import type { PlannedSession } from "../domain/session";
import type {
  LearningItem,
  LearningTerm,
  RecapCorrection,
} from "../domain/learning";
import {
  BASE_LANGUAGE,
  DEFAULT_TARGET_LANGUAGE_ID,
  TARGET_LANGUAGES,
  type LanguageProfile,
  type TargetLanguageId,
} from "../domain/languages";

interface LanguageMockContent {
  lessonTerms: LearningTerm[];
  recentItems: LearningItem[];
  prompt: string;
  connectorObjective: string;
  correction: RecapCorrection;
}

const languageContent: Record<TargetLanguageId, LanguageMockContent> = {
  mandarin: {
    lessonTerms: [
      { targetText: "先", pronunciation: "xiān", meaning: "first" },
      { targetText: "后来", pronunciation: "hòulái", meaning: "later" },
      { targetText: "最后", pronunciation: "zuìhòu", meaning: "finally" },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "最近",
        pronunciation: "zuìjìn",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "然后",
        pronunciation: "ránhòu",
        meaning: "then / afterward",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "有一点儿",
        pronunciation: "yǒu yìdiǎnr",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "你下班以后做了什么？",
    connectorObjective: "Use 然后 to connect ideas",
    correction: {
      before: "我去朋友家，然后我们吃饭。",
      after: "我去了朋友家，然后我们一起吃了饭。",
      explanation:
        "Use 了 to mark the completed events. 一起 makes the shared action clearer.",
    },
  },
  spanish: {
    lessonTerms: [
      { targetText: "primero", meaning: "first" },
      { targetText: "luego", meaning: "then / later" },
      { targetText: "al final", meaning: "finally" },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "últimamente",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "entonces",
        meaning: "then / so",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "un poco",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "¿Qué hiciste después del trabajo?",
    connectorObjective: "Use luego to connect ideas",
    correction: {
      before: "Yo fui a la casa de mi amigo, luego comimos.",
      after: "Fui a casa de mi amigo y luego comimos juntos.",
      explanation:
        "The subject pronoun is optional here. Juntos makes the shared action explicit.",
    },
  },
  french: {
    lessonTerms: [
      { targetText: "d’abord", meaning: "first" },
      { targetText: "ensuite", meaning: "then / next" },
      { targetText: "enfin", meaning: "finally" },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "récemment",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "puis",
        meaning: "then",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "un peu",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "Qu’est-ce que tu as fait après le travail ?",
    connectorObjective: "Use ensuite to connect ideas",
    correction: {
      before: "Je suis allé à la maison de mon ami, puis nous avons mangé.",
      after: "Je suis allé chez mon ami, puis nous avons mangé ensemble.",
      explanation:
        "Use chez for going to someone’s home. Ensemble makes the shared action clearer.",
    },
  },
  portuguese: {
    lessonTerms: [
      { targetText: "primeiro", meaning: "first" },
      { targetText: "depois", meaning: "then / later" },
      { targetText: "por fim", meaning: "finally" },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "recentemente",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "então",
        meaning: "then / so",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "um pouco",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "O que você fez depois do trabalho?",
    connectorObjective: "Use depois to connect ideas",
    correction: {
      before: "Eu fui na casa do meu amigo, depois comemos.",
      after: "Fui à casa do meu amigo e depois comemos juntos.",
      explanation:
        "Use fui à casa in this context. Juntos makes the shared action explicit.",
    },
  },
  japanese: {
    lessonTerms: [
      { targetText: "まず", pronunciation: "mazu", meaning: "first" },
      {
        targetText: "それから",
        pronunciation: "sorekara",
        meaning: "then / after that",
      },
      {
        targetText: "最後に",
        pronunciation: "saigo ni",
        meaning: "finally",
      },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "最近",
        pronunciation: "saikin",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "それから",
        pronunciation: "sorekara",
        meaning: "then / after that",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "少し",
        pronunciation: "sukoshi",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "仕事の後で何をしましたか？",
    connectorObjective: "Use それから to connect ideas",
    correction: {
      before: "友達の家に行く、それから食べました。",
      after: "友達の家に行って、それから一緒に食べました。",
      explanation:
        "Use the て-form to connect the completed actions. 一緒に clarifies that you ate together.",
    },
  },
  korean: {
    lessonTerms: [
      { targetText: "먼저", pronunciation: "meonjeo", meaning: "first" },
      {
        targetText: "그다음에",
        pronunciation: "geudaeume",
        meaning: "then / next",
      },
      {
        targetText: "마지막으로",
        pronunciation: "majimageuro",
        meaning: "finally",
      },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "최근에",
        pronunciation: "choegeune",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "그다음에",
        pronunciation: "geudaeume",
        meaning: "then / next",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "조금",
        pronunciation: "jogeum",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "퇴근 후에 무엇을 했어요?",
    connectorObjective: "Use 그다음에 to connect ideas",
    correction: {
      before: "친구 집에 갔어요, 그리고 밥을 먹었어요.",
      after: "친구 집에 가서 같이 밥을 먹었어요.",
      explanation:
        "Use 가서 to connect the actions naturally. 같이 makes it clear that you ate together.",
    },
  },
  vietnamese: {
    lessonTerms: [
      { targetText: "đầu tiên", meaning: "first" },
      { targetText: "sau đó", meaning: "then / after that" },
      { targetText: "cuối cùng", meaning: "finally" },
    ],
    recentItems: [
      {
        id: "item-1",
        targetText: "gần đây",
        meaning: "recently",
        state: "demonstrated",
      },
      {
        id: "item-2",
        targetText: "sau đó",
        meaning: "then / after that",
        state: "practiced",
      },
      {
        id: "item-3",
        targetText: "một chút",
        meaning: "a little bit",
        state: "retained",
      },
    ],
    prompt: "Bạn đã làm gì sau giờ làm việc?",
    connectorObjective: "Use sau đó to connect ideas",
    correction: {
      before: "Tôi đi nhà bạn, sau đó chúng tôi ăn.",
      after: "Tôi đến nhà bạn, sau đó chúng tôi ăn cùng nhau.",
      explanation:
        "Use đến for arriving at your friend’s home. Cùng nhau clarifies that you ate together.",
    },
  },
};

const pause = async (signal?: AbortSignal): Promise<void> => {
  await new Promise<void>((resolve, reject) => {
    const finish = () => {
      signal?.removeEventListener("abort", abort);
      resolve();
    };
    const abort = () => {
      window.clearTimeout(timeoutId);
      reject(new DOMException("Request aborted", "AbortError"));
    };
    const timeoutId = window.setTimeout(finish, 180);

    if (signal?.aborted) {
      abort();
      return;
    }

    signal?.addEventListener("abort", abort, { once: true });
  });
};

export function createMockWebAppGateway(
  targetLanguageId: TargetLanguageId = DEFAULT_TARGET_LANGUAGE_ID,
  startIncomplete = false,
): WebAppGateway {
  const languageProfile: LanguageProfile = {
    id: `${BASE_LANGUAGE.id}-${targetLanguageId}`,
    baseLanguageId: BASE_LANGUAGE.id,
    targetLanguageId,
  };
  const startingPreferences = {
    correctionPreference: "balanced" as const,
    tutorPace: "level" as const,
    captionsEnabled: false,
    timezone: "America/New_York",
    interests: [],
    learningGoal: "Practice everyday conversation.",
    speakingContext: "Casual conversations with people I know.",
    learningNotes: "",
    version: 1,
  };
  let currentLearner: CurrentLearner = {
    user: {
      id: "b25fdaa6-4362-4c47-851a-ad667118c0ac",
      email: "jason.tan@gmail.com",
      displayName: "Jason Tan",
      status: "active",
    },
    version: 1,
    onboarding: { complete: !startIncomplete },
    activeLanguageProfile: startIncomplete ? null : {
      ...languageProfile,
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
    preferences: startIncomplete ? null : startingPreferences,
    csrfToken: "mock-csrf-token",
  };
  const completedKeys = new Map<string, string>();
  const plannedSessions = new Map<string, PlannedSession>();
  const sessionKeys = new Map<string, { payload: string; id: string }>();
  const languagePairs: LanguagePair[] = TARGET_LANGUAGES.map((target) => ({
    baseLanguageId: BASE_LANGUAGE.id,
    targetLanguageId: target.id,
    baseLanguageName: BASE_LANGUAGE.name,
    targetLanguageName: target.name,
    targetNativeName: target.nativeName,
    available: target.id === "mandarin",
  }));

  const getContent = (languageProfileId: string): LanguageMockContent => {
    if (languageProfileId !== languageProfile.id) {
      throw new Error(`Unknown language profile: ${languageProfileId}`);
    }

    return languageContent[languageProfile.targetLanguageId];
  };

  return {
    async getCurrentLearner(signal) {
      await pause(signal);

      return currentLearner;
    },

    async getLanguagePairs(signal) {
      await pause(signal);
      return languagePairs;
    },

    async createLanguageProfile(command, signal) {
      await pause(signal);
      const payload = JSON.stringify({ ...command, idempotencyKey: undefined, csrfToken: undefined });
      const previous = completedKeys.get(command.idempotencyKey);
      if (previous && previous !== payload) throw new Error("This key was already used.");
      if (previous) return currentLearner;
      if (command.baseLanguageId !== "english" || command.targetLanguageId !== "mandarin") {
        throw new Error("This language course is not available.");
      }
      completedKeys.set(command.idempotencyKey, payload);
      currentLearner = {
        ...currentLearner,
        version: currentLearner.version + 1,
        onboarding: { complete: true },
        activeLanguageProfile: {
          ...languageProfile,
          status: "active",
          languageSelectionConfirmed: true,
          version: 1,
          learning: {
            mode: command.startingChoice === "fluent" ? "practice" : "learning",
            startingChoice: command.startingChoice,
            provisionalLevel: command.startingChoice === "fluent" ? null
              : command.startingChoice === "unsure" ? "beginner" : command.startingChoice,
            version: 1,
          },
        },
        preferences: {
          ...startingPreferences,
          correctionPreference: command.correctionPreference,
          tutorPace: command.tutorPace,
          timezone: command.timezone,
          interests: command.interests,
          learningGoal: command.learningGoal,
          speakingContext: command.speakingContext,
          learningNotes: command.learningNotes,
        },
      };
      return currentLearner;
    },

    async updatePreferences(command, signal) {
      await pause(signal);
      if (currentLearner.preferences === null) throw new Error("Complete your setup first.");
      if (command.expectedVersion !== currentLearner.preferences.version) {
        throw new Error("Preferences changed since they were read.");
      }

      currentLearner = {
        ...currentLearner,
        preferences: {
          ...currentLearner.preferences,
          ...command.changes,
          version: currentLearner.preferences.version + 1,
        },
      };
      return currentLearner;
    },

    async logout(_csrfToken, signal) {
      await pause(signal);
    },

    async createSession(command, signal) {
      await pause(signal);
      if (!currentLearner.onboarding.complete || command.languageProfileId !== languageProfile.id) {
        throw new Error("Complete your language setup first.");
      }
      const payload = JSON.stringify({
        languageProfileId: command.languageProfileId,
        topic: command.topic,
        requestedWords: command.requestedWords,
      });
      const previous = sessionKeys.get(command.idempotencyKey);
      if (previous && previous.payload !== payload) throw new Error("This key was already used.");
      if (previous) {
        const existing = plannedSessions.get(previous.id);
        if (existing) return existing;
      }
      if (plannedSessions.size > 0) throw new Error("No voice session is available right now.");
      const id = crypto.randomUUID();
      const now = new Date();
      const focus = command.topic
        ? `Have a conversation about ${command.topic}.`
        : `Have a conversation in ${targetLanguageId}.`;
      const session: PlannedSession = {
        id,
        state: "planned",
        rowVersion: 3,
        connectedLimitMs: 1_200_000,
        connectedMs: 0,
        reservationExpiresAt: new Date(now.getTime() + 10 * 60_000).toISOString(),
        objective: focus,
        planPreview: { objectives: [focus] },
        mode: currentLearner.activeLanguageProfile?.learning.mode ?? "learning",
        createdAt: now.toISOString(),
      };
      plannedSessions.set(id, session);
      sessionKeys.set(command.idempotencyKey, { payload, id });
      return session;
    },

    async getSession(sessionId, signal) {
      await pause(signal);
      const session = plannedSessions.get(sessionId);
      if (!session) throw new Error("The session was not found.");
      return session;
    },

    async getVoiceAvailability(signal) {
      await pause(signal);
      return { available: false, maxCallSeconds: 600 };
    },

    async getDashboard(languageProfileId, signal) {
      await pause(signal);
      const content = getContent(languageProfileId);

      return {
        learner: {
          displayName: "Jason",
          level: "Beginner",
          levelDescription:
            "You can handle short, familiar exchanges with a little support.",
        },
        entitlement: {
          label: "Basic plan",
          sessionsRemaining: 2,
          sessionsIncluded: 2,
          resetLabel: "Resets Monday",
        },
        suggestedFocus: {
          eyebrow: "Suggested for today",
          title: "Talk about your week",
          description:
            "Practice linking a few events with time words and natural follow-up questions.",
        },
        lessonPreview: {
          label: "Lesson 09",
          terms: content.lessonTerms,
          prompt: content.prompt,
        },
        dueReviewCount: 4,
        recentItems: content.recentItems,
        recentSessions: [
          {
            id: "session-8f3",
            title: "Weekend plans",
            completedAtLabel: "August 29",
            durationMinutes: 16,
            status: "ready",
          },
          {
            id: "session-7b1",
            title: "Food and cooking",
            completedAtLabel: "August 25",
            durationMinutes: 12,
            status: "ready",
          },
        ],
      };
    },

    async getRecap(sessionId, languageProfileId, signal) {
      await pause(signal);
      const content = getContent(languageProfileId);

      return {
        id: sessionId,
        title: "Weekend plans",
        completedAtLabel: "August 29",
        durationMinutes: 16,
        summary:
          "You talked about visiting friends and planning a quiet Sunday. You kept the conversation moving with short follow-up questions.",
        objectives: [
          { label: "Describe a recent event", outcome: "demonstrated" },
          { label: content.connectorObjective, outcome: "attempted" },
        ],
        corrections: [content.correction],
        nextFocus: "Practice telling a short sequence of past events.",
      };
    },

    async getMemories(languageProfileId, signal) {
      await pause(signal);
      getContent(languageProfileId);

      return [
        {
          id: "memory-1",
          label: "Enjoys cooking",
          detail: "You mentioned that you like trying simple noodle recipes.",
          sourceLabel: "Food and cooking session",
          expiresLabel: "Expires September 24",
        },
        {
          id: "memory-2",
          label: "Learning for travel",
          detail:
            "You want to feel comfortable having everyday conversations while traveling.",
          sourceLabel: "Introductory session",
          expiresLabel: "Kept as a learning preference",
        },
      ];
    },
  };
}

export const mockWebAppGateway = createMockWebAppGateway(
  DEFAULT_TARGET_LANGUAGE_ID,
  import.meta.env.VITE_MOCK_ONBOARDING === "true",
);

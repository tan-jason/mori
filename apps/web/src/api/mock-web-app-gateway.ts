import type { WebAppGateway } from "./web-app-gateway";

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

export const mockWebAppGateway: WebAppGateway = {
  async getDashboard(signal) {
    await pause(signal);

    return {
      learner: {
        displayName: "Jason",
        level: "Learning Beginner",
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
      dueReviewCount: 4,
      recentItems: [
        {
          id: "item-1",
          hanzi: "最近",
          pinyin: "zuìjìn",
          meaning: "recently",
          state: "demonstrated",
        },
        {
          id: "item-2",
          hanzi: "然后",
          pinyin: "ránhòu",
          meaning: "then / afterward",
          state: "practiced",
        },
        {
          id: "item-3",
          hanzi: "有一点儿",
          pinyin: "yǒu yìdiǎnr",
          meaning: "a little bit",
          state: "retained",
        },
      ],
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

  async getRecap(sessionId, signal) {
    await pause(signal);

    return {
      id: sessionId,
      title: "Weekend plans",
      completedAtLabel: "August 29",
      durationMinutes: 16,
      summary:
        "You talked about visiting friends and planning a quiet Sunday. You kept the conversation moving with short follow-up questions.",
      objectives: [
        { label: "Describe a recent event", outcome: "demonstrated" },
        { label: "Use 然后 to connect ideas", outcome: "attempted" },
      ],
      corrections: [
        {
          before: "我去朋友家，然后我们吃饭。",
          after: "我去了朋友家，然后我们一起吃了饭。",
          explanation:
            "Use 了 to mark the completed events. 一起 makes the shared action clearer.",
        },
      ],
      nextFocus: "Practice telling a short sequence of past events.",
    };
  },

  async getMemories(signal) {
    await pause(signal);

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
        detail: "You want to feel comfortable having everyday conversations while traveling.",
        sourceLabel: "Introductory session",
        expiresLabel: "Kept as a learning preference",
      },
    ];
  },
};

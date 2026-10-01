import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";
import { SessionPage } from "./session-page";
import type { RealtimeSessionFactory, RealtimeSessionState } from "../../realtime/realtime-session";

describe("SessionPage", () => {
  it("shows the profile language without making it directly configurable", async () => {
    render(
      <AppProviders
        dependencies={{ gateway: createMockWebAppGateway("japanese") }}
      >
        <MemoryRouter>
          <LanguageProfileProvider>
            <SessionPage />
          </LanguageProfileProvider>
        </MemoryRouter>
      </AppProviders>,
    );

    expect(await screen.findByText("Voice practice is unavailable")).toBeVisible();
    expect(screen.getByRole("button", { name: "Begin session" })).toBeDisabled();
    expect(screen.getByText("English")).toBeVisible();
    expect(screen.getByText("Japanese")).toBeVisible();
    expect(screen.queryByLabelText("Language to learn")).not.toBeInTheDocument();
    expect(screen.getByText(/keep the conversation in Japanese/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Change corrections" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });

  it("uses the saved plan before opening the voice transport", async () => {
    const gateway = createMockWebAppGateway();
    vi.spyOn(gateway, "getVoiceAvailability").mockResolvedValue({ available: true, maxCallSeconds: 120 });
    const createSession = vi.spyOn(gateway, "createSession");
    const events: string[] = [];
    const realtime: RealtimeSessionFactory = {
      available: true,
      create() {
        let state: RealtimeSessionState = "idle";
        const listeners = new Set<(next: RealtimeSessionState) => void>();
        return {
          get state() { return state; },
          subscribe(listener) {
            listeners.add(listener);
            listener(state);
            return () => { listeners.delete(listener); };
          },
          connect() {
            events.push("connect");
            state = "connected";
            for (const listener of listeners) listener(state);
            return Promise.resolve();
          },
          end() {
            state = "ended";
            for (const listener of listeners) listener(state);
            return Promise.resolve();
          },
          setPlaybackRate() { return Promise.resolve(); },
        };
      },
    };
    render(
      <AppProviders dependencies={{ gateway, realtime }}>
        <MemoryRouter>
          <LanguageProfileProvider><SessionPage /></LanguageProfileProvider>
        </MemoryRouter>
      </AppProviders>,
    );
    const user = userEvent.setup();
    expect(await screen.findByText("2:00")).toBeVisible();
    await user.type(await screen.findByLabelText(/something you want to talk about/i), "my weekend");
    await user.type(screen.getByLabelText(/words to practice/i), "market, recipe");
    await user.click(screen.getByRole("button", { name: "Begin session" }));

    expect(await screen.findByText("Your conversation focus")).toBeVisible();
    expect(await screen.findByRole("button", { name: "End conversation" })).toBeVisible();
    expect(createSession).toHaveBeenCalledWith(expect.objectContaining({
      topic: "my weekend", requestedWords: ["market", "recipe"],
    }));
    expect(events).toEqual(["connect"]);
  });
});

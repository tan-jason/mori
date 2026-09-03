import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";
import { SessionPage } from "./session-page";

describe("SessionPage", () => {
  it("shows the profile language without making it directly configurable", async () => {
    render(
      <AppProviders
        dependencies={{ gateway: createMockWebAppGateway("japanese") }}
      >
        <LanguageProfileProvider>
          <MemoryRouter>
            <SessionPage />
          </MemoryRouter>
        </LanguageProfileProvider>
      </AppProviders>,
    );

    expect(await screen.findByText("Voice practice is coming soon")).toBeVisible();
    expect(screen.getByRole("button", { name: "Begin session" })).toBeDisabled();
    expect(screen.getByText("English")).toBeVisible();
    expect(screen.getByText("Japanese")).toBeVisible();
    expect(screen.queryByLabelText("Language to learn")).not.toBeInTheDocument();
    expect(screen.getByText(/keep the conversation in Japanese/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "Change" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });
});

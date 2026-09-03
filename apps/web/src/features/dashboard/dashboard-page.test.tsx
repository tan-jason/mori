import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";
import { DashboardPage } from "./dashboard-page";

describe("DashboardPage", () => {
  it("renders the core learner dashboard from the gateway", async () => {
    render(
      <AppProviders>
        <LanguageProfileProvider>
          <MemoryRouter>
            <DashboardPage />
          </MemoryRouter>
        </LanguageProfileProvider>
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Nǐ hǎo, Jason." })).toBeVisible();
    expect(screen.getByRole("link", { name: /start conversation/i })).toHaveAttribute(
      "href",
      "/session",
    );
    expect(screen.getByText("2 voice sessions available")).toBeVisible();
    expect(screen.getByText("最近")).toBeVisible();
    expect(screen.getByLabelText("Today’s word bank")).toBeVisible();
  });

  it("renders target-language content from the active language profile", async () => {
    render(
      <AppProviders
        dependencies={{ gateway: createMockWebAppGateway("spanish") }}
      >
        <LanguageProfileProvider>
          <MemoryRouter>
            <DashboardPage />
          </MemoryRouter>
        </LanguageProfileProvider>
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Hola, Jason." })).toBeVisible();
    expect(await screen.findByText("últimamente")).toBeVisible();
    expect(screen.getByText(/¿Qué hiciste después del trabajo\?/)).toBeVisible();
    expect(screen.queryByLabelText("Language to learn")).not.toBeInTheDocument();
  });
});

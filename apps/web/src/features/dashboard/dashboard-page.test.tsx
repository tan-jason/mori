import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppProviders } from "../../app/app-providers";
import { DashboardPage } from "./dashboard-page";

describe("DashboardPage", () => {
  it("renders the core learner dashboard from the gateway", async () => {
    render(
      <AppProviders>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Nǐ hǎo, Jason." })).toBeVisible();
    expect(screen.getByRole("link", { name: /start conversation/i })).toHaveAttribute(
      "href",
      "/session",
    );
    expect(screen.getByText("2 voice sessions available")).toBeVisible();
    expect(screen.getByText("最近")).toBeVisible();
  });
});

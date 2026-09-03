import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";
import { ProfilePage } from "./profile-page";

describe("ProfilePage", () => {
  it("renders account, language, and tutor profile settings", async () => {
    render(
      <AppProviders
        dependencies={{ gateway: createMockWebAppGateway("vietnamese") }}
      >
        <LanguageProfileProvider>
          <MemoryRouter>
            <ProfilePage />
          </MemoryRouter>
        </LanguageProfileProvider>
      </AppProviders>,
    );

    expect(await screen.findByLabelText("Full name")).toHaveValue("Jason Tan");
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Base language")).toBeDisabled();
    expect(screen.getByLabelText("Language to learn")).toBeDisabled();
    expect(screen.getByLabelText("Language to learn")).toHaveTextContent(
      "Vietnamese · Tiếng Việt",
    );
    expect(screen.getByText("Learning Beginner")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("shows feedback when preferences are saved", async () => {
    const user = userEvent.setup();
    render(
      <AppProviders>
        <LanguageProfileProvider>
          <MemoryRouter>
            <ProfilePage />
          </MemoryRouter>
        </LanguageProfileProvider>
      </AppProviders>,
    );

    await screen.findByLabelText("Corrections");
    await user.selectOptions(screen.getByLabelText("Corrections"), "frequent");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(screen.getByRole("status")).toHaveTextContent("Preferences saved");
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ProfilePage } from "./profile-page";

describe("ProfilePage", () => {
  it("renders account, language, and tutor profile settings", () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Full name")).toHaveValue("Jason Tan");
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Base language")).toBeDisabled();
    expect(screen.getByLabelText("Language to learn")).toBeDisabled();
    expect(screen.getByText("Learning Beginner")).toBeVisible();
  });

  it("shows feedback when preferences are saved", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText("Corrections"), "frequent");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(screen.getByRole("status")).toHaveTextContent("Preferences saved");
  });
});

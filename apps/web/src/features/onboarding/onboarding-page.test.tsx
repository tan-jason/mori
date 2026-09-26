import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";

describe("explicit onboarding", () => {
  it("requires explicit choices and lands on the Study desk after confirmation", async () => {
    const user = userEvent.setup();
    const gateway = createMockWebAppGateway("mandarin", true);
    const router = createMemoryRouter(
      [
        {
          path: "/onboarding",
          element: <LanguageProfileProvider><div /></LanguageProfileProvider>,
        },
        {
          path: "/",
          element: <LanguageProfileProvider><h1>Study desk</h1></LanguageProfileProvider>,
        },
        {
          path: "/session",
          element: <LanguageProfileProvider><h1>Voice session</h1></LanguageProfileProvider>,
        },
      ],
      { initialEntries: ["/session"] },
    );
    render(<AppProviders dependencies={{ gateway }}><RouterProvider router={router} /></AppProviders>);

    expect(await screen.findByRole("heading", { name: "Choose your languages" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/onboarding");
    expect(screen.queryByRole("heading", { name: "Voice session" })).not.toBeInTheDocument();
    await screen.findByLabelText("Language for help");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose both languages");

    await user.selectOptions(screen.getByLabelText("Language for help"), "english");
    const target = screen.getByLabelText("Language to practice");
    expect(within(target).getByRole("option", { name: /Spanish.*not available yet/ })).toBeDisabled();
    await user.selectOptions(target, "mandarin");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "Where would you like to begin?" })).toBeVisible();
    await user.click(screen.getByRole("radio", { name: /I'm not sure/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(screen.getByLabelText(/Things you enjoy talking about/), "Cooking, city walks");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("I'm not sure - provisional Beginner")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Create my profile" }));
    expect(await screen.findByRole("heading", { name: "Study desk" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/");
    const learner = await gateway.getCurrentLearner();
    expect(learner.activeLanguageProfile?.learning).toMatchObject({
      mode: "learning", startingChoice: "unsure", provisionalLevel: "beginner",
    });
    expect(learner.preferences?.interests).toEqual(["Cooking", "city walks"]);
  });
});

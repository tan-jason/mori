import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createMockWebAppGateway } from "../../api/mock-web-app-gateway";
import { AppProviders } from "../../app/app-providers";
import { LanguageProfileProvider } from "../../app/language-profile-provider";
import { MemoriesPage } from "./memories-page";

describe("Learner File", () => {
  it("labels captured entries and lets the learner correct and delete them", async () => {
    const user = userEvent.setup();
    const gateway = createMockWebAppGateway();
    render(
      <AppProviders dependencies={{ gateway }}>
        <MemoryRouter><LanguageProfileProvider><MemoriesPage /></LanguageProfileProvider></MemoryRouter>
      </AppProviders>,
    );

    const learning = await screen.findByText("Used a time phrase to describe a recent event.");
    expect(screen.getByText("Learning")).toBeVisible();
    expect(screen.getByText("Insight")).toBeVisible();
    const card = learning.closest("article");
    expect(card).not.toBeNull();
    await user.click(within(card as HTMLElement).getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Edit learning"));
    await user.type(screen.getByLabelText("Edit learning"), "I described a recent event.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(screen.queryByLabelText("Edit learning")).not.toBeInTheDocument();
      expect(screen.getByText("I described a recent event.")).toBeVisible();
    });
    expect((await gateway.getLearnerFile("english-mandarin")).entries[0]?.text).toBe("I described a recent event.");

    const updatedCard = screen.getByText("I described a recent event.").closest("article");
    await user.click(within(updatedCard as HTMLElement).getByRole("button", { name: "Delete" }));
    await user.click(within(updatedCard as HTMLElement).getByRole("button", { name: "Delete learning" }));
    expect(screen.getByText("Interested in food.")).toBeVisible();
    await waitFor(() => expect(screen.queryByText("I described a recent event.")).not.toBeInTheDocument());
  });
});

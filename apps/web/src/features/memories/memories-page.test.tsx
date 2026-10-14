import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
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
  it("edits and deletes account insights through their own API", async () => {
    const user = userEvent.setup();
    const gateway = createMockWebAppGateway();
    const edit = vi.spyOn(gateway, "editUserInsight");
    const remove = vi.spyOn(gateway, "deleteUserInsight");
    render(<AppProviders dependencies={{ gateway }}><MemoryRouter><LanguageProfileProvider><MemoriesPage /></LanguageProfileProvider></MemoryRouter></AppProviders>);
    const insight = await screen.findByText("Interested in food.");
    await user.click(within(insight.closest("article")!).getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Edit insight"));
    await user.type(screen.getByLabelText("Edit insight"), "Enjoys baking bread.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByLabelText("Edit insight")).not.toBeInTheDocument());
    const updated = await screen.findByText("Enjoys baking bread.");
    expect(edit).toHaveBeenCalledOnce();
    await user.click(within(updated.closest("article")!).getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete insight" }));
    await waitFor(() => expect(screen.queryByText("Enjoys baking bread.")).not.toBeInTheDocument());
    expect(remove).toHaveBeenCalledOnce();
    expect((await gateway.getLearnerFile("english-mandarin")).entries).toHaveLength(1);
  });

  it("keeps insights account-owned while learnings stay in their profile", async () => {
    const gateway = createMockWebAppGateway();
    expect((await gateway.getLearnerFile("english-mandarin")).entries).toHaveLength(1);
    await gateway.createLanguageProfile({ baseLanguageId: "english", targetLanguageId: "french", startingChoice: "beginner", correctionPreference: "balanced", tutorPace: "level", timezone: "America/New_York", interests: [], learningNotes: "", learningGoal: "Travel", speakingContext: "Everyday conversations", idempotencyKey: "switch-french", csrfToken: "csrf" });
    expect((await gateway.getLearnerFile("english-french")).entries).toEqual([]);
    expect((await gateway.getUserInsights()).entries[0]?.text).toBe("Interested in food.");
  });

  it("keeps learnings visible when insight loading fails", async () => {
    const gateway = createMockWebAppGateway();
    vi.spyOn(gateway, "getUserInsights").mockRejectedValue(new Error("Insights unavailable"));
    render(<AppProviders dependencies={{ gateway }}><MemoryRouter><LanguageProfileProvider><MemoriesPage /></LanguageProfileProvider></MemoryRouter></AppProviders>);
    expect(await screen.findByText("Used a time phrase to describe a recent event.")).toBeVisible();
    expect(await screen.findByText("Your insights could not be loaded.", {}, { timeout: 3000 })).toBeVisible();
  });

});

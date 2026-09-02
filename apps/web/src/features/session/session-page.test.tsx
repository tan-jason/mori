import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SessionPage } from "./session-page";

describe("SessionPage", () => {
  it("makes the realtime integration status explicit", () => {
    render(
      <MemoryRouter>
        <SessionPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Connection scaffold only")).toBeVisible();
    expect(screen.getByRole("button", { name: "Begin session" })).toBeDisabled();
    expect(screen.getByLabelText("Base language")).toBeDisabled();
    expect(screen.getByLabelText("Learning")).toBeDisabled();
  });
});

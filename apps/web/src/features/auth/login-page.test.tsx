import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LoginPage } from "./login-page";

describe("LoginPage", () => {
  it("offers the Google sign-in entry point", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /learn it by speaking it/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /continue with google/i })).toHaveAttribute(
      "href",
      "/",
    );
  });
});

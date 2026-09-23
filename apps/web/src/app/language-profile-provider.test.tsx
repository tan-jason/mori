import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiError } from "../api/api-error";
import { createMockWebAppGateway } from "../api/mock-web-app-gateway";
import { AppProviders } from "./app-providers";
import { LanguageProfileProvider } from "./language-profile-provider";

describe("LanguageProfileProvider", () => {
  it("redirects an unauthenticated learner to sign in", async () => {
    const mockGateway = createMockWebAppGateway();
    const gateway = {
      ...mockGateway,
      getCurrentLearner: () =>
        Promise.reject(
          new ApiError(
            401,
            "authentication_required",
            "Authentication is required.",
          ),
        ),
    };
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <LanguageProfileProvider>
              <p>Private learner page</p>
            </LanguageProfileProvider>
          ),
        },
        { path: "/login", element: <h1>Sign in to Mori</h1> },
      ],
      { initialEntries: ["/"] },
    );

    render(
      <AppProviders dependencies={{ gateway }}>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    expect(
      await screen.findByRole("heading", { name: "Sign in to Mori" }),
    ).toBeVisible();
    expect(screen.queryByText("Private learner page")).not.toBeInTheDocument();
  });
});

import { createBrowserRouter } from "react-router-dom";
import { LanguageProfileProvider } from "./language-profile-provider";
import { AppShell } from "../components/app-shell";
import { RouteErrorPage } from "../components/route-error-page";
import { DashboardPage } from "../features/dashboard/dashboard-page";
import { LoginPage } from "../features/auth/login-page";
import { MemoriesPage } from "../features/memories/memories-page";
import { ProfilePage } from "../features/profile/profile-page";
import { RecapPage } from "../features/recap/recap-page";
import { SessionPage } from "../features/session/session-page";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/",
    element: (
      <LanguageProfileProvider>
        <AppShell />
      </LanguageProfileProvider>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "session", element: <SessionPage /> },
      { path: "recaps/:sessionId", element: <RecapPage /> },
      { path: "memories", element: <MemoriesPage /> },
      { path: "profile", element: <ProfilePage /> },
    ],
  },
]);

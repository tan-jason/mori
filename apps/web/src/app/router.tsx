import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "../components/app-shell";
import { RouteErrorPage } from "../components/route-error-page";
import { DashboardPage } from "../features/dashboard/dashboard-page";
import { MemoriesPage } from "../features/memories/memories-page";
import { RecapPage } from "../features/recap/recap-page";
import { SessionPage } from "../features/session/session-page";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "session", element: <SessionPage /> },
      { path: "recaps/:sessionId", element: <RecapPage /> },
      { path: "memories", element: <MemoriesPage /> },
    ],
  },
]);

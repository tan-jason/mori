import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type PropsWithChildren } from "react";
import { createBackendWebAppGateway } from "../api/backend-web-app-gateway";
import { mockWebAppGateway } from "../api/mock-web-app-gateway";
import {
  AppDependenciesContext,
  type AppDependencies,
} from "./app-dependencies";

const defaultDependencies: AppDependencies = {
  gateway:
    import.meta.env.MODE === "test" || import.meta.env.VITE_USE_MOCK_API === "true"
      ? mockWebAppGateway
      : createBackendWebAppGateway(),
};

interface AppProvidersProps extends PropsWithChildren {
  dependencies?: AppDependencies;
}

export function AppProviders({
  children,
  dependencies = defaultDependencies,
}: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <AppDependenciesContext.Provider value={dependencies}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </AppDependenciesContext.Provider>
  );
}

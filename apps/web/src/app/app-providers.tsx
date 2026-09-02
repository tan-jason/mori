import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type PropsWithChildren } from "react";
import { mockWebAppGateway } from "../api/mock-web-app-gateway";
import {
  AppDependenciesContext,
  type AppDependencies,
} from "./app-dependencies";

const defaultDependencies: AppDependencies = {
  gateway: mockWebAppGateway,
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

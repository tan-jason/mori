import { createContext, useContext } from "react";
import type { WebAppGateway } from "../api/web-app-gateway";

export interface AppDependencies {
  gateway: WebAppGateway;
}

export const AppDependenciesContext = createContext<AppDependencies | null>(null);

export function useAppDependencies(): AppDependencies {
  const dependencies = useContext(AppDependenciesContext);

  if (!dependencies) {
    throw new Error("useAppDependencies must be used within AppProviders.");
  }

  return dependencies;
}

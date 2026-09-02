import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";

export const dashboardQueryKey = ["dashboard"] as const;

export function useDashboard() {
  const { gateway } = useAppDependencies();

  return useQuery({
    queryKey: dashboardQueryKey,
    queryFn: ({ signal }) => gateway.getDashboard(signal),
  });
}

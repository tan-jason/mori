import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";

export const dashboardQueryKey = (languageProfileId: string) =>
  ["dashboard", languageProfileId] as const;

export function useDashboard() {
  const { gateway } = useAppDependencies();
  const { languageProfile } = useLanguageProfile();

  return useQuery({
    queryKey: dashboardQueryKey(languageProfile.id),
    queryFn: ({ signal }) => gateway.getDashboard(languageProfile.id, signal),
  });
}

import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";

export function useRecap(sessionId: string) {
  const { gateway } = useAppDependencies();
  const { languageProfile } = useLanguageProfile();

  return useQuery({
    queryKey: ["recap", languageProfile.id, sessionId],
    queryFn: ({ signal }) =>
      gateway.getRecap(sessionId, languageProfile.id, signal),
  });
}

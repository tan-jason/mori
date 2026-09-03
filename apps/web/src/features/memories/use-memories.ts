import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";

export function useMemories() {
  const { gateway } = useAppDependencies();
  const { languageProfile } = useLanguageProfile();

  return useQuery({
    queryKey: ["memories", languageProfile.id],
    queryFn: ({ signal }) => gateway.getMemories(languageProfile.id, signal),
  });
}

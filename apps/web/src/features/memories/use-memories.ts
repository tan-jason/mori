import { useInfiniteQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";

export function useLearnerFile() {
  const { gateway } = useAppDependencies();
  const { languageProfile } = useLanguageProfile();

  return useInfiniteQuery({
    queryKey: ["learner-file", languageProfile.id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => gateway.getLearnerFile(languageProfile.id, pageParam, signal),
    getNextPageParam: (page) => page.nextCursor,
  });
}

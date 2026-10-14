import { useInfiniteQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";
import { useLanguageProfile } from "../../app/use-language-profile";
import { useLearnerSession } from "../../app/use-learner-session";

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

export function useUserInsights() {
  const { gateway } = useAppDependencies();
  const { learner } = useLearnerSession();

  return useInfiniteQuery({
    queryKey: ["user-insights", learner.user.id],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => gateway.getUserInsights(pageParam, signal),
    getNextPageParam: (page) => page.nextCursor,
  });
}

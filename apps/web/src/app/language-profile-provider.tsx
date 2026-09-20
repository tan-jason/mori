import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import { isAuthenticationRequired } from "../api/api-error";
import { PageErrorState, PageLoadingState } from "../components/async-state";
import { getTargetLanguage } from "../domain/languages";
import { useAppDependencies } from "./app-dependencies";
import { LanguageProfileContext } from "./language-profile-context";
import { LearnerSessionContext } from "./learner-session-context";

const currentLearnerQueryKey = ["current-learner"] as const;

export function LanguageProfileProvider({ children }: PropsWithChildren) {
  const { gateway } = useAppDependencies();
  const queryClient = useQueryClient();
  const learner = useQuery({
    queryKey: currentLearnerQueryKey,
    queryFn: ({ signal }) => gateway.getCurrentLearner(signal),
    staleTime: Number.POSITIVE_INFINITY,
    retry: (failureCount, error) =>
      !isAuthenticationRequired(error) && failureCount < 1,
  });

  if (learner.isPending) {
    return (
      <main className="page-shell">
        <PageLoadingState />
      </main>
    );
  }

  if (learner.isError) {
    if (isAuthenticationRequired(learner.error)) {
      return <Navigate to="/login" replace />;
    }

    return (
      <main className="page-shell">
        <PageErrorState
          title="Your profile could not be loaded"
          message="We could not reach your learner profile. Please try again."
          onRetry={() => void learner.refetch()}
        />
      </main>
    );
  }

  const currentLearner = learner.data;
  const languageProfile = currentLearner.activeLanguageProfile;
  const languageValue = {
    languageProfile,
    targetLanguage: getTargetLanguage(languageProfile.targetLanguageId),
  };
  const learnerValue = {
    learner: currentLearner,
    replaceLearner: (updatedLearner: typeof currentLearner) => {
      queryClient.setQueryData(currentLearnerQueryKey, updatedLearner);
    },
  };

  return (
    <LearnerSessionContext.Provider value={learnerValue}>
      <LanguageProfileContext.Provider value={languageValue}>
        {children}
      </LanguageProfileContext.Provider>
    </LearnerSessionContext.Provider>
  );
}

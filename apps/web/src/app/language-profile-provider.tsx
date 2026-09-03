import { useQuery } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { PageErrorState, PageLoadingState } from "../components/async-state";
import { getTargetLanguage } from "../domain/languages";
import { useAppDependencies } from "./app-dependencies";
import { LanguageProfileContext } from "./language-profile-context";

const languageProfileQueryKey = ["active-language-profile"] as const;

export function LanguageProfileProvider({ children }: PropsWithChildren) {
  const { gateway } = useAppDependencies();
  const profile = useQuery({
    queryKey: languageProfileQueryKey,
    queryFn: ({ signal }) => gateway.getActiveLanguageProfile(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  if (profile.isPending) {
    return (
      <main className="page-shell">
        <PageLoadingState />
      </main>
    );
  }

  if (profile.isError) {
    return (
      <main className="page-shell">
        <PageErrorState
          title="Your course could not be loaded"
          message="We could not load your active language profile. Please try again."
          onRetry={() => void profile.refetch()}
        />
      </main>
    );
  }

  const languageProfile = profile.data;
  const value = {
    languageProfile,
    targetLanguage: getTargetLanguage(languageProfile.targetLanguageId),
  };

  return (
    <LanguageProfileContext.Provider value={value}>
      {children}
    </LanguageProfileContext.Provider>
  );
}

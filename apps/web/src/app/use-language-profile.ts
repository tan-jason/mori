import { useContext } from "react";
import {
  LanguageProfileContext,
  type LanguageProfileContextValue,
} from "./language-profile-context";

export function useLanguageProfile(): LanguageProfileContextValue {
  const context = useContext(LanguageProfileContext);

  if (!context) {
    throw new Error("useLanguageProfile must be used within AppProviders.");
  }

  return context;
}

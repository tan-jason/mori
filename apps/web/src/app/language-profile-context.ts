import { createContext } from "react";
import type { LanguageProfile, TargetLanguage } from "../domain/languages";

export interface LanguageProfileContextValue {
  languageProfile: LanguageProfile;
  targetLanguage: TargetLanguage;
}

export const LanguageProfileContext =
  createContext<LanguageProfileContextValue | null>(null);

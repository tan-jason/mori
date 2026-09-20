import { useContext } from "react";
import {
  LearnerSessionContext,
  type LearnerSessionContextValue,
} from "./learner-session-context";

export function useLearnerSession(): LearnerSessionContextValue {
  const context = useContext(LearnerSessionContext);

  if (!context) {
    throw new Error("useLearnerSession must be used within LanguageProfileProvider.");
  }

  return context;
}

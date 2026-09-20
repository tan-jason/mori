import { createContext } from "react";
import type { CurrentLearner } from "../domain/identity";

export interface LearnerSessionContextValue {
  learner: CurrentLearner;
  replaceLearner: (learner: CurrentLearner) => void;
}

export const LearnerSessionContext =
  createContext<LearnerSessionContextValue | null>(null);

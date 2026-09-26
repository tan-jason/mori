import { createContext } from "react";
import type { CurrentLearner, ReadyLearner } from "../domain/identity";

export interface LearnerSessionContextValue {
  learner: ReadyLearner;
  replaceLearner: (learner: CurrentLearner) => void;
}

export const LearnerSessionContext =
  createContext<LearnerSessionContextValue | null>(null);

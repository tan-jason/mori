import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";

export function useRecap(sessionId: string) {
  const { gateway } = useAppDependencies();

  return useQuery({
    queryKey: ["recap", sessionId],
    queryFn: ({ signal }) => gateway.getRecap(sessionId, signal),
  });
}

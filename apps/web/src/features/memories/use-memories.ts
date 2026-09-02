import { useQuery } from "@tanstack/react-query";
import { useAppDependencies } from "../../app/app-dependencies";

export function useMemories() {
  const { gateway } = useAppDependencies();

  return useQuery({
    queryKey: ["memories"],
    queryFn: ({ signal }) => gateway.getMemories(signal),
  });
}

import { useQuery } from "@tanstack/react-query";
import { fetchDashboardBundle } from "@/hooks/client/dashboard/useDashboardClient";

export const DASHBOARD_QUERY_KEY = ["dashboard", "bundle"] as const;

export function useDashboardQuery(enabled = true) {
  return useQuery({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: fetchDashboardBundle,
    enabled,
    refetchInterval: (query) => {
      const workerRunning = Boolean(query.state.data?.system.worker.running);
      return workerRunning ? 3000 : 10000;
    },
  });
}

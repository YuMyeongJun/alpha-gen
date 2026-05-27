import { useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/modules/apiClient";
import { DASHBOARD_QUERY_KEY } from "@/hooks/client/dashboard/useDashboardQuery";
import type { IAdminActionReq } from "@/models/interface/req/IOpsConsoleReq";

async function invalidateDashboard(queryClient: ReturnType<typeof useQueryClient>) {
  await queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
}

export function useSystemMutations() {
  const queryClient = useQueryClient();

  const clearCache = useMutation({
    mutationFn: (payload: IAdminActionReq) =>
      apiClient.post("/api/system/cache/clear", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const refreshKisToken = useMutation({
    mutationFn: (payload: IAdminActionReq) =>
      apiClient.post("/api/system/kis/token/refresh", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const resetDatabase = useMutation({
    mutationFn: (payload: IAdminActionReq) =>
      apiClient.post("/api/system/db/reset", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const syncBroker = useMutation({
    mutationFn: (session: string = "KR") =>
      apiClient.post("/api/broker/sync", null, { params: { session } }).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  return { clearCache, refreshKisToken, resetDatabase, syncBroker };
}

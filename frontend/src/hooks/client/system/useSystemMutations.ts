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

  const importPosition = useMutation({
    mutationFn: (payload: { stock_code: string; session: "KR" | "US"; qty: number; avg_price: number; stock_name?: string }) =>
      apiClient.post("/api/portfolio/position/import", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const paperOrder = useMutation({
    mutationFn: (payload: { stock_code: string; session: "KR" | "US"; side: "buy" | "sell"; qty: number }) =>
      apiClient.post("/api/orders/paper", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  /** UI에서 직접 누르는 매수/매도 — 리스크 휴면 모드 무시, KIS 실행 시도 */
  const manualOrder = useMutation({
    mutationFn: (payload: { stock_code: string; session: "KR" | "US"; side: "buy" | "sell"; qty: number }) =>
      apiClient.post("/api/orders/manual", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  /** 앱에서 직접 매도 후 DB 추적만 제거 */
  const removePosition = useMutation({
    mutationFn: (payload: { stock_code: string; session: "KR" | "US" }) =>
      apiClient.delete(`/api/portfolio/position/${payload.session}/${payload.stock_code}`).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  /** 리스크 휴면 모드 수동 해제 */
  const exitSleepMode = useMutation({
    mutationFn: () => apiClient.post("/api/risk/sleep-mode/exit").then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  /** 자산 추이 기록(가라 데이터 포함) 초기화 */
  const clearEquity = useMutation({
    mutationFn: (payload: IAdminActionReq) =>
      apiClient.post("/api/system/equity/clear", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  return { clearCache, refreshKisToken, resetDatabase, syncBroker, importPosition, paperOrder, manualOrder, exitSleepMode, clearEquity, removePosition };
}

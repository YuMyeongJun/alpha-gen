import { useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/modules/apiClient";
import { DASHBOARD_QUERY_KEY } from "@/hooks/client/dashboard/useDashboardQuery";
import type {
  IAgentCycleReq,
  IAnalysisRefreshReq,
  IBacktestRunReq,
  IEmergencyStopReq,
  IPaperOrderReq,
  IStageUpdateReq,
  IWorkerStartReq,
} from "@/models/interface/req/IOpsConsoleReq";

async function invalidateDashboard(queryClient: ReturnType<typeof useQueryClient>) {
  await queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
}

export function useOpsMutations() {
  const queryClient = useQueryClient();

  const refreshAnalysis = useMutation({
    mutationFn: (payload: IAnalysisRefreshReq) =>
      apiClient.post("/api/analysis/refresh", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const runCycle = useMutation({
    mutationFn: (payload: IAgentCycleReq) =>
      apiClient.post("/api/agent/cycle", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const startWorker = useMutation({
    mutationFn: (payload: IWorkerStartReq) =>
      apiClient.post("/api/agent/worker/start", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const stopWorker = useMutation({
    mutationFn: () => apiClient.post("/api/agent/worker/stop", {}).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const setEmergencyStop = useMutation({
    mutationFn: (payload: IEmergencyStopReq) =>
      apiClient.post("/api/safety/emergency-stop", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const setStage = useMutation({
    mutationFn: (payload: IStageUpdateReq) =>
      apiClient.post("/api/safety/stage", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const runBacktest = useMutation({
    mutationFn: (payload: IBacktestRunReq) =>
      apiClient.post("/api/backtests/run", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  const placePaperOrder = useMutation({
    mutationFn: (payload: IPaperOrderReq) =>
      apiClient.post("/api/orders/paper", payload).then((res) => res.data),
    onSuccess: () => invalidateDashboard(queryClient),
  });

  return {
    refreshAnalysis,
    runCycle,
    startWorker,
    stopWorker,
    setEmergencyStop,
    setStage,
    runBacktest,
    placePaperOrder,
  };
}

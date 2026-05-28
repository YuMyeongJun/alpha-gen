import apiClient from "@/modules/apiClient";
import type {
  IAuditListRes,
  IBacktestsListRes,
  IDashboardBundleRes,
  IOrdersListRes,
  IPortfolioRes,
  ISafetyStatusRes,
  ISignalsListRes,
  ISystemStatusRes,
} from "@/models/interface/res/IDashboardRes";

export async function fetchDashboardBundle(): Promise<IDashboardBundleRes> {
  const [portfolio, signals, orders, backtests, system, safety, audit] = await Promise.all([
    apiClient.get<IPortfolioRes>("/api/portfolio"),
    apiClient.get<ISignalsListRes>("/api/signals?limit=50"),
    apiClient.get<IOrdersListRes>("/api/orders"),
    apiClient.get<IBacktestsListRes>("/api/backtests"),
    apiClient.get<ISystemStatusRes>("/api/system/status"),
    apiClient.get<ISafetyStatusRes>("/api/safety"),
    apiClient.get<IAuditListRes>("/api/audit"),
  ]);

  return {
    portfolio: portfolio.data,
    signals: signals.data,
    orders: orders.data,
    backtests: backtests.data,
    system: system.data,
    safety: safety.data,
    audit: audit.data,
  };
}

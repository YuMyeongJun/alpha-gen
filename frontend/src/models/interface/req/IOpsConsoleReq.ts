import type { MarketSession, OperatingStage, OrderSide } from "@/models/type/commonType";

export interface IEmergencyStopReq {
  enabled: boolean;
  reason?: string;
}

export interface IStageUpdateReq {
  stage: OperatingStage;
}

export interface IWorkerStartReq {
  interval_sec: number;
  session: MarketSession;
  place_orders: boolean;
}

export interface IAgentCycleReq {
  session: MarketSession;
  force_refresh: boolean;
  place_orders: boolean;
}

export interface IAnalysisRefreshReq {
  session: MarketSession;
  force_refresh: boolean;
}

export interface IPaperOrderReq {
  stock_code: string;
  session: string;
  side: OrderSide;
  qty: number;
}

export interface IBacktestRunReq {
  days: number;
  initial_cash: number;
}

export interface IAdminActionReq {
  confirm: boolean;
  reason: string;
}

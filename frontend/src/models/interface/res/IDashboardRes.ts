import type { OperatingStage } from "@/models/type/commonType";

export interface IEmergencyStopRes {
  enabled: boolean;
  reason?: string;
}

export interface ISafetyPolicyRes {
  stage: OperatingStage;
  auto_orders_enabled: boolean;
  live_orders_enabled: boolean;
  shadow_mode?: boolean;
  emergency_stop: IEmergencyStopRes;
  limits?: Record<string, number>;
}

export interface ISafetyStatusRes {
  policy: ISafetyPolicyRes;
  audit?: unknown[];
}

export interface IWorkerStatusRes {
  running: boolean;
  interval_sec?: number;
  session?: string;
  place_orders?: boolean;
  started_at?: string | null;
  cycle_count?: number;
  current_status?: string;
  last_cycle_at?: string | null;
  next_cycle_at?: string | null;
  last_summary?: string;
  last_signal_count?: number;
  last_order_count?: number;
  last_result?: {
    last_signal_count?: number;
    last_order_count?: number;
  };
}

export interface IAuditEventRes {
  id?: number;
  scope?: string;
  event_type: string;
  severity?: string;
  message?: string;
  session?: string;
  created_at?: string;
}

export interface IAuditListRes {
  events: IAuditEventRes[];
}

export interface IPositionRes {
  stock_code: string;
  stock_name: string;
  session: string;
  qty: number;
  avg_price: number;
  last_price: number;
}

export interface IPortfolioRes {
  total_asset: number;
  cash: number;
  positions: IPositionRes[];
  equity?: Array<{ total_asset: number }>;
  risk?: {
    drawdown_pct?: number;
    stop_loss_count?: number;
    sleep_mode?: boolean;
  };
}

export interface ISignalRes {
  stock_code: string;
  stock_name: string;
  session: string;
  buy_signal: boolean;
  sentiment_score: number;
  sentiment_label: string;
  current_price: number;
  technical_signal?: boolean;
  technical_reason?: string;
}

export interface ISignalsListRes {
  signals: ISignalRes[];
}

export interface IOrderRes {
  stock_code: string;
  stock_name?: string;
  session: string;
  side: string;
  status: string;
  qty: number;
  executed_price?: number;
  requested_price?: number;
  realized_pnl?: number | null;
  attempt_count?: number;
  message?: string;
  created_at?: string;
}

export interface IOrdersListRes {
  orders: IOrderRes[];
}

export interface IBacktestRunRes {
  created_at?: string;
  summary: {
    total_return_pct: number;
    win_rate: number;
    trade_count: number;
    gross_pnl: number;
  };
}

export interface IBacktestsListRes {
  runs: IBacktestRunRes[];
}

export interface ISystemStatusRes {
  config: {
    mock_mode: boolean;
    mock_mode_reason?: string;
    allow_live_trading: boolean;
    operating_stage: OperatingStage;
    auto_order_enabled?: boolean;
  };
  diagnostics: {
    summary: string;
    integrations: {
      missing_config?: string[];
    };
  };
  worker: IWorkerStatusRes;
}

export interface IDashboardBundleRes {
  portfolio: IPortfolioRes;
  signals: ISignalsListRes;
  orders: IOrdersListRes;
  backtests: IBacktestsListRes;
  system: ISystemStatusRes;
  safety: ISafetyStatusRes;
  audit: IAuditListRes;
}

import type { OperatingStage } from "@/models/type/commonType";

export interface IEmergencyStopRes {
  enabled: boolean;
  reason?: string;
}

export interface ISafetyPolicyUsageRes {
  orders_today: number;
  live_orders_today: number;
  live_orders_cycle: number;
}

export interface ISafetyPolicyRes {
  stage: OperatingStage;
  auto_orders_enabled: boolean;
  live_orders_enabled: boolean;
  shadow_mode?: boolean;
  emergency_stop: IEmergencyStopRes;
  limits?: Record<string, number>;
  usage?: ISafetyPolicyUsageRes;
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
  cycle_id?: string;
  current_status?: string;
  last_cycle_at?: string | null;
  next_cycle_at?: string | null;
  last_summary?: string;
  last_signal_count?: number;
  last_order_count?: number;
  last_result?: {
    cycle_id?: string;
    last_signal_count?: number;
    last_order_count?: number;
    last_buy_candidate_count?: number;
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
  orders?: IOrderRes[];
  equity?: Array<{ total_asset: number; created_at?: string }>;
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
  sentiment_reason?: string;
  current_price: number;
  change_pct?: number;
  technical_signal?: boolean;
  technical_reason?: string;
  analyzed_at?: string;
  quote?: Record<string, unknown>;
  technical?: Record<string, unknown>;
  sentiment?: Record<string, unknown>;
}

export interface ISignalsListRes {
  signals: ISignalRes[];
}

export interface IOrderRes {
  id?: string;
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
  id?: string;
  created_at?: string;
  parameters?: Record<string, unknown>;
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

export interface IKisTokenMetaRes {
  cached?: boolean;
  expires_at?: string | null;
  auth_blocked_reason?: string | null;
  api_degraded_reason?: string | null;
}

export interface ISystemDiagnosticsRes {
  ok?: boolean;
  summary: string;
  environment?: {
    python?: string;
    platform?: string;
    mock_mode?: boolean;
    operating_stage?: OperatingStage;
  };
  storage?: {
    db_path?: string;
    db_exists?: boolean;
    db_size_bytes?: number;
    paper_cash?: number;
    positions?: number;
    audit_events?: number;
  };
  integrations?: {
    kis_configured?: boolean;
    claude_configured?: boolean;
    frontend_present?: boolean;
    missing_config?: string[];
    kis_token?: IKisTokenMetaRes;
  };
  packages?: Record<string, { ok: boolean; error?: string }>;
}

export interface ISystemStatusRes {
  config: {
    mock_mode: boolean;
    mock_mode_reason?: string;
    allow_live_trading: boolean;
    operating_stage: OperatingStage;
    auto_order_enabled?: boolean;
    db_path?: string;
  };
  diagnostics: ISystemDiagnosticsRes;
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

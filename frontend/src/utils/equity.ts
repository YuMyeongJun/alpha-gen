import type { IEquityPoint } from "@/components/pages/OpsConsole/charts/EquityChart";
import type { IPortfolioRes } from "@/models/interface/res/IDashboardRes";
import { formatCompactDateTime } from "@/utils/format";

export type EquityPeriod = "1D" | "1W" | "1M" | "ALL";

const PERIOD_MS: Record<Exclude<EquityPeriod, "ALL">, number> = {
  "1D": 24 * 60 * 60 * 1000,
  "1W": 7 * 24 * 60 * 60 * 1000,
  "1M": 30 * 24 * 60 * 60 * 1000,
};

export function filterEquityByPeriod(
  equity: Array<{ total_asset: number; created_at?: string }>,
  period: EquityPeriod,
): Array<{ total_asset: number; created_at?: string }> {
  if (period === "ALL" || !equity.length) return equity;
  const cutoff = Date.now() - PERIOD_MS[period];
  const filtered = equity.filter((point) => {
    if (!point.created_at) return true;
    const ts = Date.parse(point.created_at);
    return Number.isFinite(ts) && ts >= cutoff;
  });
  return filtered.length ? filtered : equity.slice(-1);
}

export function buildEquitySeries(
  portfolio: IPortfolioRes,
  period: EquityPeriod = "ALL",
  nowLabel = "현재",
): { data: IEquityPoint[]; baseline: number } {
  const equity = filterEquityByPeriod(portfolio.equity || [], period);
  const data: IEquityPoint[] = equity.map((point, index) => ({
    t: point.created_at ? formatCompactDateTime(point.created_at) : `#${index + 1}`,
    v: Number(point.total_asset || 0),
  }));

  if (!data.length && portfolio.total_asset) {
    data.push({ t: nowLabel, v: Number(portfolio.total_asset) });
  }

  const baseline = data.length ? data[0].v : Number(portfolio.total_asset || portfolio.cash || 0);

  return { data, baseline };
}

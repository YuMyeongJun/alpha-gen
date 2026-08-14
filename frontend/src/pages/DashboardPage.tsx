import { useMemo, useState } from "react";
import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { Badge, Card, Metric, MetricGrid, PageHeader } from "@/components/common";
import { EquityChart } from "@/components/pages/OpsConsole/charts/EquityChart";
import { SignalBars } from "@/components/pages/OpsConsole/charts/SignalBars";
import { OpsConsoleRail } from "@/components/pages/OpsConsole/OpsConsoleRail";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";
import { buildEquitySeries, filterEquityByPeriod, type EquityPeriod } from "@/utils/equity";
import { currency, formatDateTime, formatRelative } from "@/utils/format";

const PERIODS: EquityPeriod[] = ["1D", "1W", "1M", "ALL"];

const PERIOD_LABEL_KEYS: Record<EquityPeriod, string> = {
  "1D": "panels.dashboard.period1D",
  "1W": "panels.dashboard.period1W",
  "1M": "panels.dashboard.period1M",
  ALL: "panels.dashboard.periodAll",
};

export const DashboardPage = () => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const { data } = useOpsConsoleContext();
  const { portfolio, signals, system, safety } = data;
  const [equityPeriod, setEquityPeriod] = useState<EquityPeriod>("ALL");
  const workerRunning = Boolean(system.worker.running);
  const recentSignals = signals.signals || [];
  const buyCount = recentSignals.filter((s) => s.buy_signal).length;
  const sellCount = recentSignals.filter((s) => !s.buy_signal && Number(s.sentiment_score) < -0.2).length;
  const watchCount = Math.max(recentSignals.length - buyCount - sellCount, 0);
  const drawdown = portfolio.risk?.drawdown_pct || 0;
  const { data: equityData, baseline } = useMemo(
    () => buildEquitySeries(portfolio, equityPeriod, t("chart.current")),
    [portfolio, equityPeriod, t],
  );

  const equityRangeLabel = useMemo(() => {
    const pts = equityData.length;
    if (!pts) return null;
    if (pts === 1) return `${equityData[0].t} · 1포인트`;
    return `${equityData[0].t} ~ ${equityData[pts - 1].t} · ${pts}포인트`;
  }, [equityData]);

  const periodPointCounts = useMemo(() => {
    const raw = portfolio.equity || [];
    return (["1D", "1W", "1M", "ALL"] as EquityPeriod[]).reduce<Record<EquityPeriod, number>>(
      (acc, p) => {
        acc[p] = filterEquityByPeriod(raw, p).length;
        return acc;
      },
      {} as Record<EquityPeriod, number>,
    );
  }, [portfolio.equity]);

  const pnlPct =
    baseline > 0 ? ((Number(portfolio.total_asset) - baseline) / baseline) * 100 : 0;
  const cashWeight =
    portfolio.total_asset > 0 ? (Number(portfolio.cash) / Number(portfolio.total_asset)) * 100 : 100;
  const worker = system.worker;
  const lastResult = worker.last_result || {};
  const buyCandidates = lastResult.last_buy_candidate_count ?? buyCount;
  const usage = safety.policy.usage;
  const dailyLimit = safety.policy.limits?.live_max_orders_per_day;
  const ordersToday = usage?.orders_today;

  return (
    <>
      <Helmet>
        <title>
          {t("pages.dashboard.title")} · {t("app.title")}
        </title>
      </Helmet>

      <PageHeader
        eyebrow={t("brand.consoleEyebrow")}
        title={t("panels.dashboard.title")}
        subtitle={t("panels.dashboard.subtitle")}
      />

      <MetricGrid columns={4}>
        <Metric
          size="hero"
          label={t("panels.dashboard.totalAsset")}
          value={currency(portfolio.total_asset)}
          unit={t("common.currencyUnit")}
          sub={
            <>
              <span style={{ color: pnlPct >= 0 ? "var(--green-600)" : "var(--red-600)" }}>
                {pnlPct >= 0 ? "+" : ""}
                {pnlPct.toFixed(2)}%
              </span>{" "}
              · {t("common.vsBaseline")}
            </>
          }
        />
        <Metric
          label={t("panels.dashboard.cash")}
          value={currency(portfolio.cash)}
          unit={t("common.currencyUnit")}
          sub={
            <>
              <span className="muted">{t("common.cashWeight")} </span>
              {cashWeight.toFixed(1)}%
            </>
          }
        />
        <Metric
          label={t("panels.dashboard.workerStatus")}
          tone={workerRunning ? undefined : "danger"}
          value={labels.workerRunning(workerRunning)}
          right={
            workerRunning ? (
              <Badge tone="green" dot>
                {t("domain.worker.running")}
              </Badge>
            ) : (
              <Badge tone="red" solid>
                {t("domain.worker.stopped")}
              </Badge>
            )
          }
          sub={
            <>
              {t("sidebar.lastRun")}{" "}
              <span className="mono">{formatRelative(worker.last_cycle_at)}</span>
            </>
          }
        />
        <Metric
          label={t("panels.dashboard.riskStatus")}
          value={Number(drawdown).toFixed(2)}
          unit="%"
          right={
            <Badge tone="blue" dot>
              {portfolio.risk?.sleep_mode ? t("domain.risk.sleepMode") : t("domain.risk.optionMode")}
            </Badge>
          }
          sub={
            <>
              {t("panels.dashboard.dailyLimit")}{" "}
              <span className="mono">
                {ordersToday != null && dailyLimit != null ? `${ordersToday}/${dailyLimit}` : dailyLimit ?? "-"}
              </span>{" "}
              · {t("panels.dashboard.quoteStaleness")} {safety.policy.limits?.quote_staleness_sec ?? "-"}
              {t("sidebar.seconds")}
            </>
          }
        />
      </MetricGrid>

      <div className="dash-grid">
        <div className="dash-grid__main">
          <Card
            eyebrow={t("panels.dashboard.equityEyebrow")}
            title={t("panels.dashboard.equityTitle")}
            right={
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                <div className="row" style={{ gap: 6 }}>
                  {PERIODS.map((period) => {
                    const count = periodPointCounts[period] ?? 0;
                    return (
                      <button
                        key={period}
                        type="button"
                        className={`btn btn--sm${equityPeriod === period ? "" : " btn--ghost"}`}
                        style={equityPeriod === period ? undefined : { background: "var(--bg-tertiary)" }}
                        onClick={() => setEquityPeriod(period)}
                        title={`${count}포인트`}
                      >
                        {t(PERIOD_LABEL_KEYS[period])}
                        <span
                          className="muted"
                          style={{ fontSize: 10, marginLeft: 3, opacity: 0.7 }}
                        >
                          {count}
                        </span>
                      </button>
                    );
                  })}
                </div>
                {equityRangeLabel && (
                  <span className="muted" style={{ fontSize: 11 }}>
                    {equityRangeLabel}
                  </span>
                )}
              </div>
            }
          >
            <EquityChart data={equityData} baseline={baseline} height={236} />
          </Card>

          <div className="grid-2">
            <Card
              eyebrow={t("panels.dashboard.signalMixEyebrow")}
              title={t("panels.dashboard.signalMixTitle")}
              right={
                <span className="muted" style={{ fontSize: 12 }}>
                  {t("panels.dashboard.signalTotal", { count: recentSignals.length })}
                </span>
              }
            >
              <SignalBars
                rows={[
                  { key: "watch", label: labels.signalVerdict("watch"), value: watchCount, tone: "gray" },
                  { key: "buy", label: labels.signalVerdict("buy"), value: buyCount, tone: "green" },
                  { key: "sell", label: labels.signalVerdict("sell"), value: sellCount, tone: "red" },
                  {
                    key: "skip",
                    label: labels.signalVerdict("skip"),
                    value: Math.max(recentSignals.length - buyCount - sellCount - watchCount, 0),
                    tone: "gray",
                  },
                ]}
              />
            </Card>
            <Card
              eyebrow={t("panels.dashboard.latestCycleEyebrow")}
              title={t("panels.dashboard.latestCycleTitle")}
              right={
                <Badge tone="green" dot>
                  {workerRunning ? t("domain.cycleStatus.running") : t("domain.cycleStatus.done")}
                </Badge>
              }
            >
              <dl className="kv">
                <dt>{t("panels.dashboard.cycleId")}</dt>
                <dd className="mono">{worker.cycle_id || lastResult.cycle_id || "-"}</dd>
                <dt>{t("panels.dashboard.cycleCount")}</dt>
                <dd>{worker.cycle_count || 0}</dd>
                <dt>{t("panels.dashboard.executedAt")}</dt>
                <dd>{formatDateTime(worker.last_cycle_at)}</dd>
                <dt>{t("panels.dashboard.signalsGenerated")}</dt>
                <dd>
                  {t("panels.dashboard.signalsGeneratedDetail", {
                    count: lastResult.last_signal_count ?? worker.last_signal_count ?? 0,
                    buy: buyCandidates,
                  })}
                </dd>
                <dt>{t("panels.dashboard.ordersPlaced")}</dt>
                <dd>
                  {t("panels.dashboard.ordersPlacedDetail", {
                    count: lastResult.last_order_count ?? worker.last_order_count ?? 0,
                    stage: labels.operatingStage(safety.policy.stage),
                  })}
                </dd>
                <dt>{t("panels.dashboard.nextRun")}</dt>
                <dd>{formatDateTime(worker.next_cycle_at)}</dd>
              </dl>
            </Card>
          </div>
        </div>

        <OpsConsoleRail data={data} />
      </div>
    </>
  );
};

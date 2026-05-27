import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DetailModal, Icon, PageHeader } from "@/components/common";
import type { IBacktestRunRes } from "@/models/interface/res/IDashboardRes";
import { currency, formatCompactDateTime, percent, toneClass } from "@/utils/format";

export interface IBacktestsPanelProps {
  runs: IBacktestRunRes[];
  onRunBacktest: () => void;
}

export const BacktestsPanel = ({ runs, onRunBacktest }: IBacktestsPanelProps) => {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<IBacktestRunRes | null>(null);
  const avgWin =
    runs.length > 0 ? runs.reduce((sum, r) => sum + Number(r.summary.win_rate), 0) / runs.length : 0;

  return (
    <>
      <PageHeader
        title={t("panels.backtests.title")}
        subtitle={t("panels.backtests.subtitle")}
        right={
          <button type="button" className="btn btn--primary" onClick={onRunBacktest}>
            <Icon name="play" size={12} />
            {t("panels.backtests.runButton")}
          </button>
        }
      />

      {runs.length > 0 && (
        <div className="row" style={{ gap: 8, marginBottom: 14 }}>
          <Badge tone="gray">{t("panels.backtests.recentCount", { count: runs.length })}</Badge>
          <Badge tone={Number(runs[0].summary.total_return_pct) >= 0 ? "green" : "red"} dot>
            {t("panels.backtests.latestReturn", { pct: percent(runs[0].summary.total_return_pct) })}
          </Badge>
          <Badge tone="gray">{t("panels.backtests.avgWinRate", { pct: avgWin.toFixed(0) })}</Badge>
        </div>
      )}

      <Card>
        {!runs.length ? (
          <div className="empty-state">{t("panels.backtests.empty")}</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.backtests.colTime")}</th>
                <th className="num">{t("panels.backtests.colReturn")}</th>
                <th className="num">{t("panels.backtests.colWinRate")}</th>
                <th className="num">{t("panels.backtests.colTrades")}</th>
                <th className="num">{t("panels.backtests.colPnl")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((run, index) => {
                const ret = Number(run.summary.total_return_pct);
                const pnl = Number(run.summary.gross_pnl);
                return (
                  <tr key={run.id || `${run.created_at}-${index}`}>
                    <td>{formatCompactDateTime(run.created_at)}</td>
                    <td className="num">
                      {ret >= 0 ? (
                        <Badge tone="green">{percent(ret)}</Badge>
                      ) : (
                        <Badge tone="red">{percent(ret)}</Badge>
                      )}
                    </td>
                    <td className="num mono">{Number(run.summary.win_rate).toFixed(1)}%</td>
                    <td className="num mono">
                      {run.summary.trade_count}
                      {t("common.countUnit")}
                    </td>
                    <td className={`num ${toneClass(pnl)}`}>
                      {pnl >= 0 ? "+" : ""}
                      {currency(pnl)}
                      {t("common.currencyUnit")}
                    </td>
                    <td className="num">
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => setSelected(run)}>
                        {t("panels.backtests.report")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <DetailModal
        open={Boolean(selected)}
        title={t("panels.backtests.reportTitle")}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <dl className="kv" style={{ marginBottom: 12 }}>
              <dt>{t("panels.backtests.runId")}</dt>
              <dd className="mono">{selected.id || "-"}</dd>
              <dt>{t("panels.backtests.colTime")}</dt>
              <dd>{formatCompactDateTime(selected.created_at)}</dd>
              <dt>{t("panels.backtests.colReturn")}</dt>
              <dd>{percent(selected.summary.total_return_pct)}</dd>
              <dt>{t("panels.backtests.colWinRate")}</dt>
              <dd>{Number(selected.summary.win_rate).toFixed(1)}%</dd>
              <dt>{t("panels.backtests.colTrades")}</dt>
              <dd>
                {selected.summary.trade_count}
                {t("common.countUnit")}
              </dd>
              <dt>{t("panels.backtests.colPnl")}</dt>
              <dd>
                {currency(selected.summary.gross_pnl)}
                {t("common.currencyUnit")}
              </dd>
            </dl>
            <details className="details-card" open>
              <summary>{t("panels.backtests.parametersSummary")}</summary>
              <pre className="json-view">
                {JSON.stringify({ parameters: selected.parameters, summary: selected.summary }, null, 2)}
              </pre>
            </details>
          </>
        ) : null}
      </DetailModal>
    </>
  );
};

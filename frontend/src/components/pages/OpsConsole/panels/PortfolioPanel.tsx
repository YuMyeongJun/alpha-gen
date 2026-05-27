import { useTranslation } from "react-i18next";
import { Badge, Card, Metric, PageHeader } from "@/components/common";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { buildEquitySeries } from "@/utils/equity";
import { currency, percent, toneClass } from "@/utils/format";

export interface IPortfolioPanelProps {
  portfolio: IDashboardBundleRes["portfolio"];
}

export const PortfolioPanel = ({ portfolio }: IPortfolioPanelProps) => {
  const { t } = useTranslation();
  const { baseline } = buildEquitySeries(portfolio);
  const pnlPct = baseline > 0 ? ((Number(portfolio.total_asset) - baseline) / baseline) * 100 : 0;
  const cashWeight =
    portfolio.total_asset > 0 ? (Number(portfolio.cash) / Number(portfolio.total_asset)) * 100 : 100;
  const unrealized = portfolio.positions.reduce((sum, p) => {
    const pnl = p.avg_price ? (p.last_price - p.avg_price) * p.qty : 0;
    return sum + pnl;
  }, 0);

  return (
    <>
      <PageHeader title={t("panels.portfolio.title")} subtitle={t("panels.portfolio.subtitle")} />

      <div className="grid-4" style={{ marginBottom: 14 }}>
        <Metric
          label={t("panels.portfolio.evaluated")}
          value={currency(portfolio.total_asset)}
          unit={t("common.currencyUnit")}
          sub={<span className="muted">{t("panels.portfolio.vsBaseline", { pct: percent(pnlPct) })}</span>}
        />
        <Metric
          label={t("panels.portfolio.cash")}
          value={currency(portfolio.cash)}
          unit={t("common.currencyUnit")}
          sub={<span className="muted">{t("panels.portfolio.weight", { pct: cashWeight.toFixed(1) })}</span>}
        />
        <Metric
          label={t("panels.portfolio.holdings")}
          value={portfolio.positions.length}
          unit={t("panels.portfolio.unitCount")}
          sub={
            <span className="muted">
              {t("panels.portfolio.prevDayHoldings", { count: portfolio.positions.length })}
            </span>
          }
        />
        <Metric
          label={t("panels.portfolio.unrealizedPnl")}
          value={currency(unrealized)}
          unit={t("common.currencyUnit")}
          sub={
            <span className="muted">
              {portfolio.risk?.sleep_mode ? t("panels.portfolio.sleepInactive") : t("panels.portfolio.sleepActive")}
            </span>
          }
        />
      </div>

      <Card
        title={t("panels.portfolio.positionsTitle")}
        eyebrow={t("panels.portfolio.positionsEyebrow")}
        right={<Badge tone="gray">{t("panels.portfolio.currentCount", { count: portfolio.positions.length })}</Badge>}
      >
        {portfolio.positions.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.portfolio.colName")}</th>
                <th>{t("panels.portfolio.colCode")}</th>
                <th>{t("panels.portfolio.colSession")}</th>
                <th className="num">{t("panels.portfolio.colQty")}</th>
                <th className="num">{t("panels.portfolio.colAvg")}</th>
                <th className="num">{t("panels.portfolio.colPrice")}</th>
                <th className="num">{t("panels.portfolio.colPnl")}</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((item) => {
                const pnlPctRow = item.avg_price
                  ? ((item.last_price - item.avg_price) / item.avg_price) * 100
                  : 0;
                return (
                  <tr key={`${item.stock_code}-${item.session}`}>
                    <td>{item.stock_name}</td>
                    <td className="mono">{item.stock_code}</td>
                    <td>{item.session}</td>
                    <td className="num">{item.qty}</td>
                    <td className="num">{currency(item.avg_price)}</td>
                    <td className="num">{currency(item.last_price)}</td>
                    <td className={`num ${toneClass(pnlPctRow)}`}>{percent(pnlPctRow)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            {t("panels.portfolio.empty")}
            <div className="empty-state__hint">{t("panels.portfolio.emptyHint")}</div>
          </div>
        )}
      </Card>
    </>
  );
};

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DetailModal, Metric, PageHeader } from "@/components/common";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { ISignalRes } from "@/models/interface/res/IDashboardRes";
import type { SignalVerdict } from "@/utils/domainLabels";
import { formatDateTime } from "@/utils/format";

export interface ISignalsPanelProps {
  signals: ISignalRes[];
}

function signalVerdict(signal: ISignalRes): SignalVerdict {
  if (signal.buy_signal) return "buy";
  if (Number(signal.sentiment_score) < -0.2) return "sell";
  return "watch";
}

export const SignalsPanel = ({ signals }: ISignalsPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const [selected, setSelected] = useState<ISignalRes | null>(null);
  const buyCount = signals.filter((s) => s.buy_signal).length;
  const sellCount = signals.filter((s) => signalVerdict(s) === "sell").length;
  const watchCount = Math.max(signals.length - buyCount - sellCount, 0);
  const avgBuy =
    buyCount > 0
      ? signals.filter((s) => s.buy_signal).reduce((sum, s) => sum + Number(s.sentiment_score || 0), 0) / buyCount
      : 0;

  return (
    <>
      <PageHeader title={t("panels.signals.title")} subtitle={t("panels.signals.subtitle")} />

      <div className="grid-4" style={{ marginBottom: 14 }}>
        <Metric
          label={t("panels.signals.totalSignals")}
          value={signals.length}
          unit={t("common.countUnit")}
          sub={<span className="muted">{t("panels.signals.recentCycle")}</span>}
        />
        <Metric
          label={t("panels.signals.buyCandidates")}
          value={buyCount}
          unit={t("common.countUnit")}
          right={<Badge tone="green" dot>{t("panels.signals.bullish")}</Badge>}
          sub={<span className="muted">{t("panels.signals.avgScore", { score: avgBuy.toFixed(2) })}</span>}
        />
        <Metric
          label={t("panels.signals.sellCandidates")}
          value={sellCount}
          unit={t("common.countUnit")}
          right={<Badge tone="red" dot>{t("panels.signals.bearish")}</Badge>}
          sub={<span className="muted">{t("panels.signals.bearishNote")}</span>}
        />
        <Metric
          label={labels.signalVerdict("watch")}
          value={watchCount}
          unit={t("common.countUnit")}
          sub={<span className="muted">{labels.signalVerdict("watch")}</span>}
        />
      </div>

      <Card
        title={t("panels.signals.listTitle")}
        eyebrow={t("panels.signals.eyebrow", { count: signals.length })}
      >
        {!signals.length ? (
          <div className="empty-state">{t("panels.signals.empty")}</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.signals.colSymbol")}</th>
                <th>{t("panels.signals.colVerdict")}</th>
                <th className="num">{t("panels.signals.colScore")}</th>
                <th className="num">{t("panels.signals.colPrice")}</th>
                <th className="num">{t("panels.signals.colChange")}</th>
                <th className="num">{t("panels.signals.colTechnical")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {signals.map((signal) => {
                const verdict = signalVerdict(signal);
                const changePct = Number(signal.change_pct ?? 0);
                return (
                  <tr key={`${signal.stock_code}-${signal.session}-${signal.current_price}`}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{signal.stock_name}</div>
                      <div className="mono muted">{signal.stock_code}</div>
                    </td>
                    <td>
                      <Badge tone={verdict === "buy" ? "green" : verdict === "sell" ? "red" : "gray"} dot>
                        {labels.signalVerdict(verdict)}
                      </Badge>
                    </td>
                    <td className="num mono">{Number(signal.sentiment_score).toFixed(2)}</td>
                    <td className="num">{Number(signal.current_price).toLocaleString()}</td>
                    <td className={`num ${changePct >= 0 ? "pos" : "neg"}`}>
                      {changePct >= 0 ? "+" : ""}
                      {changePct.toFixed(2)}%
                    </td>
                    <td className="num">
                      {signal.technical_signal ? t("domain.technical.pass") : t("domain.technical.hold")}
                    </td>
                    <td className="num">
                      <button type="button" className="btn btn--sm btn--ghost" onClick={() => setSelected(signal)}>
                        {t("common.detail")}
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
        title={selected ? `${selected.stock_name} (${selected.stock_code})` : t("panels.signals.detailTitle")}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <dl className="kv" style={{ marginBottom: 12 }}>
              <dt>{t("panels.signals.session")}</dt>
              <dd>{selected.session}</dd>
              <dt>{t("panels.signals.analyzedAt")}</dt>
              <dd>{formatDateTime(selected.analyzed_at)}</dd>
              <dt>{t("panels.signals.sentimentScore")}</dt>
              <dd>
                {Number(selected.sentiment_score).toFixed(2)} ({selected.sentiment_label})
              </dd>
              <dt>{t("panels.signals.sentimentReason")}</dt>
              <dd>{selected.sentiment_reason || "-"}</dd>
              <dt>{t("panels.signals.technicalVerdict")}</dt>
              <dd>{selected.technical_signal ? t("domain.technical.pass") : t("domain.technical.hold")}</dd>
              <dt>{t("panels.signals.technicalReason")}</dt>
              <dd>{selected.technical_reason || "-"}</dd>
            </dl>
            <details className="details-card">
              <summary>{t("panels.signals.rawData")}</summary>
              <pre className="json-view">
                {JSON.stringify({ quote: selected.quote, technical: selected.technical, sentiment: selected.sentiment }, null, 2)}
              </pre>
            </details>
          </>
        ) : null}
      </DetailModal>
    </>
  );
};

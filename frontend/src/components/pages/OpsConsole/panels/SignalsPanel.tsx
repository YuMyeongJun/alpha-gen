import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DetailModal, Metric, PageHeader } from "@/components/common";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { ISignalRes } from "@/models/interface/res/IDashboardRes";
import type { SignalVerdict } from "@/utils/domainLabels";
import { formatDateTime } from "@/utils/format";

export interface ISignalsPanelProps {
  signals: ISignalRes[];
}

type SessionTab = "ALL" | "KR" | "US";
type VerdictTab = "ALL" | "buy" | "sell" | "watch";

function signalVerdict(signal: ISignalRes): SignalVerdict {
  if (signal.buy_signal) return "buy";
  if (Number(signal.sentiment_score) < -0.2) return "sell";
  return "watch";
}

export const SignalsPanel = ({ signals }: ISignalsPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const [selected, setSelected] = useState<ISignalRes | null>(null);
  const [sessionTab, setSessionTab] = useState<SessionTab>("ALL");
  const [verdictTab, setVerdictTab] = useState<VerdictTab>("ALL");

  // 세션·판정 필터 적용
  const filtered = useMemo(() => {
    let list = signals;
    if (sessionTab !== "ALL") list = list.filter((s) => s.session === sessionTab);
    if (verdictTab !== "ALL") list = list.filter((s) => signalVerdict(s) === verdictTab);
    // 감성 점수 내림차순 정렬
    return [...list].sort((a, b) => Number(b.sentiment_score) - Number(a.sentiment_score));
  }, [signals, sessionTab, verdictTab]);

  // 전체 기준 요약 지표 (탭 필터와 무관하게 전체 집계)
  const buyCount   = signals.filter((s) => s.buy_signal).length;
  const sellCount  = signals.filter((s) => signalVerdict(s) === "sell").length;
  const watchCount = Math.max(signals.length - buyCount - sellCount, 0);
  const avgBuy     =
    buyCount > 0
      ? signals.filter((s) => s.buy_signal).reduce((sum, s) => sum + Number(s.sentiment_score || 0), 0) / buyCount
      : 0;

  // 탭별 종목 수 뱃지
  const countBySession = (session: SessionTab) =>
    session === "ALL" ? signals.length : signals.filter((s) => s.session === session).length;
  const countByVerdict = (verdict: VerdictTab) =>
    verdict === "ALL" ? signals.length : signals.filter((s) => signalVerdict(s) === verdict).length;

  const SESSION_TABS: { key: SessionTab; label: string }[] = [
    { key: "ALL", label: "전체" },
    { key: "KR",  label: "🇰🇷 국내" },
    { key: "US",  label: "🇺🇸 미국·유럽" },
  ];

  const VERDICT_TABS: { key: VerdictTab; label: string }[] = [
    { key: "ALL",   label: "전체" },
    { key: "buy",   label: "매수" },
    { key: "sell",  label: "매도" },
    { key: "watch", label: "관망" },
  ];

  return (
    <>
      <PageHeader title={t("panels.signals.title")} subtitle={t("panels.signals.subtitle")} />

      {/* 요약 지표 */}
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

      {/* 세션 필터 탭 */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
        {SESSION_TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`btn btn--sm${sessionTab === key ? " btn--primary" : " btn--ghost"}`}
            onClick={() => setSessionTab(key)}
          >
            {label}
            <span
              className="muted"
              style={{ fontSize: 10, marginLeft: 4, opacity: 0.75 }}
            >
              {countBySession(key)}
            </span>
          </button>
        ))}

        <span style={{ flexGrow: 1 }} />

        {/* 판정 필터 탭 */}
        {VERDICT_TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`btn btn--sm${verdictTab === key ? " btn--primary" : " btn--ghost"}`}
            onClick={() => setVerdictTab(key)}
          >
            {key === "buy" ? "🟢" : key === "sell" ? "🔴" : key === "watch" ? "⚪" : ""}{" "}
            {label}
            <span
              className="muted"
              style={{ fontSize: 10, marginLeft: 3, opacity: 0.75 }}
            >
              {countByVerdict(key)}
            </span>
          </button>
        ))}
      </div>

      {/* 시그널 테이블 */}
      <Card
        title={t("panels.signals.listTitle")}
        eyebrow={`${filtered.length} / ${signals.length}개 표시`}
      >
        {!filtered.length ? (
          <div className="empty-state">
            {signals.length === 0
              ? t("panels.signals.empty")
              : "해당 조건의 시그널이 없습니다."}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.signals.colSymbol")}</th>
                <th>세션</th>
                <th>{t("panels.signals.colVerdict")}</th>
                <th className="num">{t("panels.signals.colScore")}</th>
                <th className="num">{t("panels.signals.colPrice")}</th>
                <th className="num">{t("panels.signals.colChange")}</th>
                <th className="num">{t("panels.signals.colTechnical")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((signal) => {
                const verdict = signalVerdict(signal);
                const changePct = Number(signal.change_pct ?? 0);
                return (
                  <tr key={`${signal.stock_code}-${signal.session}-${signal.current_price}`}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{signal.stock_name}</div>
                      <div className="mono muted" style={{ fontSize: 11 }}>{signal.stock_code}</div>
                    </td>
                    <td>
                      <span className="muted" style={{ fontSize: 12 }}>
                        {signal.session === "KR" ? "🇰🇷 KR" : "🇺🇸 US"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                        <Badge tone={verdict === "buy" ? "green" : verdict === "sell" ? "red" : "gray"} dot>
                          {labels.signalVerdict(verdict)}
                        </Badge>
                        {signal.session === "US" && (verdict === "buy" || verdict === "sell") && (
                          <span title={verdict === "buy" ? "매수 추천 시 텔레그램 알림 발송" : "보유 중이면 매도 알림 발송"}>
                            <Badge tone={verdict === "buy" ? "blue" : "red"} style={{ fontSize: "0.7rem" }}>
                              📱 알림
                            </Badge>
                          </span>
                        )}
                      </div>
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
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => setSelected(signal)}
                      >
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

      {/* 상세 모달 */}
      <DetailModal
        open={Boolean(selected)}
        title={selected ? `${selected.stock_name} (${selected.stock_code})` : t("panels.signals.detailTitle")}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <dl className="kv" style={{ marginBottom: 12 }}>
              <dt>{t("panels.signals.session")}</dt>
              <dd>{selected.session === "KR" ? "🇰🇷 국내" : "🇺🇸 미국·유럽"}</dd>
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
                {JSON.stringify(
                  { quote: selected.quote, technical: selected.technical, sentiment: selected.sentiment },
                  null,
                  2,
                )}
              </pre>
            </details>
          </>
        ) : null}
      </DetailModal>
    </>
  );
};

import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import { Badge, Card, Metric, PageHeader } from "@/components/common";
import { useSystemMutations } from "@/hooks/client/system/useSystemMutations";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { buildEquitySeries } from "@/utils/equity";
import { currency, percent, toneClass } from "@/utils/format";

export interface IPortfolioPanelProps {
  portfolio: IDashboardBundleRes["portfolio"];
}

const USD_KRW = 1_350; // 환율 근사값 (표시 전용)

function toUsd(krw: number): string {
  return `$${(krw / USD_KRW).toFixed(2)}`;
}

type SessionTab = "ALL" | "KR" | "US";

type ImportForm = {
  stock_code: string;
  stock_name: string;
  session: "KR" | "US";
  qty: number;
  avg_price: number;
};

type OrderTarget = {
  stock_code: string;
  stock_name: string;
  session: "KR" | "US";
  side: "buy" | "sell";
  held_qty: number;
  last_price: number;
};

export const PortfolioPanel = ({ portfolio }: IPortfolioPanelProps) => {
  const { t } = useTranslation();
  const mutations = useSystemMutations();
  const [tab, setTab] = useState<SessionTab>("ALL");
  const [showImport, setShowImport] = useState(false);
  const [orderTarget, setOrderTarget] = useState<OrderTarget | null>(null);
  const [orderQty, setOrderQty] = useState(1);

  const importForm = useForm<ImportForm>({
    defaultValues: { stock_code: "", stock_name: "", session: "KR", qty: 1, avg_price: 0 },
  });

  const { baseline } = buildEquitySeries(portfolio);
  const pnlPct = baseline > 0 ? ((Number(portfolio.total_asset) - baseline) / baseline) * 100 : 0;
  const cashWeight =
    portfolio.total_asset > 0 ? (Number(portfolio.cash) / Number(portfolio.total_asset)) * 100 : 100;

  const allPositions = portfolio.positions ?? [];
  const krPositions = allPositions.filter((p) => p.session === "KR");
  const usPositions = allPositions.filter((p) => p.session === "US");

  const visiblePositions =
    tab === "KR" ? krPositions : tab === "US" ? usPositions : allPositions;

  const unrealized = allPositions.reduce((sum, p) => {
    const pnl = p.avg_price ? (p.last_price - p.avg_price) * p.qty : 0;
    return sum + pnl;
  }, 0);
  const krUnrealized = krPositions.reduce(
    (sum, p) => sum + (p.avg_price ? (p.last_price - p.avg_price) * p.qty : 0),
    0,
  );
  const usUnrealized = usPositions.reduce(
    (sum, p) => sum + (p.avg_price ? (p.last_price - p.avg_price) * p.qty : 0),
    0,
  );

  const syncBroker = async (session: "KR" | "US") => {
    try {
      await mutations.syncBroker.mutateAsync(session);
      toast.success(`${session} 포지션 동기화 완료`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "동기화 실패");
    }
  };

  const openOrder = (item: (typeof allPositions)[0], side: "buy" | "sell") => {
    setOrderTarget({
      stock_code: item.stock_code,
      stock_name: item.stock_name || item.stock_code,
      session: item.session as "KR" | "US",
      side,
      held_qty: item.qty,
      last_price: item.last_price,
    });
    setOrderQty(side === "sell" ? item.qty : 1);
  };

  const submitOrder = async () => {
    if (!orderTarget) return;
    try {
      const result = await mutations.manualOrder.mutateAsync({
        stock_code: orderTarget.stock_code,
        session: orderTarget.session,
        side: orderTarget.side,
        qty: orderQty,
      });
      const verb = orderTarget.side === "sell" ? "매도" : "매수";
      const via = result.broker_executed ? " (KIS 실행)" : " (DB 추적)";
      toast.success(`${orderTarget.stock_name} ${orderQty}주 ${verb} 완료${via}`);
      setOrderTarget(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "주문 실패");
    }
  };

  const exitSleepMode = async () => {
    try {
      await mutations.exitSleepMode.mutateAsync();
      toast.success("리스크 휴면 모드 해제 완료");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "해제 실패");
    }
  };

  const TABS: { key: SessionTab; label: string; count: number }[] = [
    { key: "ALL", label: "전체", count: allPositions.length },
    { key: "KR", label: "국내", count: krPositions.length },
    { key: "US", label: "해외", count: usPositions.length },
  ];

  return (
    <>
      <PageHeader title={t("panels.portfolio.title")} subtitle={t("panels.portfolio.subtitle")} />

      {/* 리스크 휴면 모드 배너 */}
      {portfolio.risk?.sleep_mode && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "10px 14px",
            marginBottom: 14,
            background: "var(--amber-50)",
            border: "1px solid var(--amber-500)",
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <span>
            ⚠️ <strong>리스크 휴면 모드 활성화</strong> — 자동 매수가 차단된 상태입니다.
          </span>
          <button
            type="button"
            className="btn btn--sm"
            disabled={mutations.exitSleepMode.isPending}
            onClick={() => void exitSleepMode()}
          >
            {mutations.exitSleepMode.isPending ? "해제 중..." : "휴면 해제"}
          </button>
        </div>
      )}

      {/* 요약 지표 */}
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
          value={allPositions.length}
          unit={t("panels.portfolio.unitCount")}
          sub={
            <span className="muted">
              국내 {krPositions.length} · 해외 {usPositions.length}
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

      {/* 국내 / 해외 요약 카드 */}
      {allPositions.length > 0 && (
        <div className="grid-2" style={{ marginBottom: 14 }}>
          <Card
            title="국내 (KR)"
            eyebrow="DOMESTIC"
            right={
              <button
                type="button"
                className="btn btn--sm"
                disabled={mutations.syncBroker.isPending}
                onClick={() => void syncBroker("KR")}
              >
                동기화
              </button>
            }
          >
            <dl className="kv">
              <dt>보유종목</dt>
              <dd>{krPositions.length}개</dd>
              <dt>평가손익</dt>
              <dd className={toneClass(krUnrealized)}>{currency(krUnrealized)}원</dd>
            </dl>
          </Card>
          <Card
            title="해외 (US)"
            eyebrow="OVERSEAS"
            right={
              <button
                type="button"
                className="btn btn--sm"
                disabled={mutations.syncBroker.isPending}
                onClick={() => void syncBroker("US")}
              >
                동기화
              </button>
            }
          >
            <dl className="kv">
              <dt>보유종목</dt>
              <dd>{usPositions.length}개</dd>
              <dt>평가손익 (원)</dt>
              <dd className={toneClass(usUnrealized)}>{currency(usUnrealized)}원</dd>
              <dt>평가손익 (달러)</dt>
              <dd className={toneClass(usUnrealized)}>{toUsd(usUnrealized)}</dd>
            </dl>
          </Card>
        </div>
      )}

      {/* 보유종목 테이블 */}
      <Card
        title="보유종목"
        eyebrow="HOLDINGS"
        right={
          <div style={{ display: "flex", gap: 4 }}>
            <button
              type="button"
              className={`btn btn--sm${showImport ? " btn--primary" : ""}`}
              onClick={() => { setShowImport(!showImport); setOrderTarget(null); }}
            >
              + 포지션 등록
            </button>
            {TABS.map(({ key, label, count }) => (
              <button
                key={key}
                type="button"
                className={`btn btn--sm${tab === key ? " btn--primary" : ""}`}
                onClick={() => setTab(key)}
              >
                {label}
                {count > 0 && (
                  <Badge tone={tab === key ? "blue" : "gray"} style={{ marginLeft: 4 }}>
                    {count}
                  </Badge>
                )}
              </button>
            ))}
          </div>
        }
      >
        {/* 포지션 등록 폼 (접힘/펼침) */}
        {showImport && (
          <div
            style={{
              background: "var(--bg-subtle)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "12px 14px",
              marginBottom: 14,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>
              외부 포지션 등록 <span className="muted" style={{ fontWeight: 400 }}>— 한투 앱 등 외부에서 직접 매수한 종목</span>
            </div>
            <form
              onSubmit={importForm.handleSubmit(async (values) => {
                try {
                  await mutations.importPosition.mutateAsync({
                    stock_code: values.stock_code.trim().toUpperCase(),
                    session: values.session,
                    qty: Number(values.qty),
                    avg_price: Number(values.avg_price),
                    stock_name: values.stock_name.trim(),
                  });
                  toast.success(`${values.stock_code.toUpperCase()} ${values.qty}주 등록 완료`);
                  importForm.reset({ stock_code: "", stock_name: "", session: "KR", qty: 1, avg_price: 0 });
                  setShowImport(false);
                } catch (e) {
                  toast.error(e instanceof Error ? e.message : "등록 실패");
                }
              })}
            >
              <div className="grid-2" style={{ gap: 8, marginBottom: 8 }}>
                <div className="field">
                  <span className="field__label">종목코드 *</span>
                  <input
                    className="input"
                    placeholder="005930 / SPRC"
                    {...importForm.register("stock_code", { required: true })}
                  />
                </div>
                <div className="field">
                  <span className="field__label">종목명 (선택)</span>
                  <input className="input" placeholder="자동 인식" {...importForm.register("stock_name")} />
                </div>
                <div className="field">
                  <span className="field__label">세션</span>
                  <select className="select" {...importForm.register("session")}>
                    <option value="KR">KR (국내)</option>
                    <option value="US">US (미국)</option>
                  </select>
                </div>
                <div className="field">
                  <span className="field__label">수량 (주) *</span>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    {...importForm.register("qty", { valueAsNumber: true, min: 1 })}
                  />
                </div>
                <div className="field" style={{ gridColumn: "1/-1" }}>
                  <span className="field__label">평균 매입가 (원) *</span>
                  <input
                    className="input"
                    type="number"
                    min={1}
                    placeholder="미국주식은 원화 환산가 입력"
                    {...importForm.register("avg_price", { valueAsNumber: true, min: 1 })}
                  />
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="submit"
                  className="btn btn--accent btn--sm"
                  disabled={mutations.importPosition.isPending}
                >
                  {mutations.importPosition.isPending ? "등록 중..." : "등록"}
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={() => setShowImport(false)}
                >
                  닫기
                </button>
              </div>
            </form>
          </div>
        )}

        {/* 보유종목 테이블 */}
        {visiblePositions.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>종목</th>
                <th>코드</th>
                <th>세션</th>
                <th className="num">수량</th>
                <th className="num">평균매입가</th>
                <th className="num">현재가</th>
                <th className="num">평가손익</th>
                <th className="num">수익률</th>
                <th style={{ width: 100 }}>관리</th>
              </tr>
            </thead>
            <tbody>
              {visiblePositions.map((item) => {
                const pnl = item.avg_price ? (item.last_price - item.avg_price) * item.qty : 0;
                const pnlPctRow = item.avg_price
                  ? ((item.last_price - item.avg_price) / item.avg_price) * 100
                  : 0;
                const isUS = item.session === "US";
                const isActive =
                  orderTarget?.stock_code === item.stock_code && orderTarget.session === item.session;
                return (
                  <tr key={`${item.stock_code}-${item.session}`} style={isActive ? { background: "var(--bg-hover)" } : undefined}>
                    <td>
                      <span style={{ fontWeight: 550 }}>{item.stock_name || item.stock_code}</span>
                    </td>
                    <td className="mono">{item.stock_code}</td>
                    <td>
                      <Badge tone={isUS ? "blue" : "green"} dot>
                        {item.session}
                      </Badge>
                    </td>
                    <td className="num">{item.qty}</td>
                    <td className="num">
                      {isUS ? (
                        <>
                          {toUsd(item.avg_price)}
                          <br />
                          <span className="muted" style={{ fontSize: 11 }}>{currency(item.avg_price)}원</span>
                        </>
                      ) : (
                        <>{currency(item.avg_price)}원</>
                      )}
                    </td>
                    <td className="num">
                      {isUS ? (
                        <>
                          {toUsd(item.last_price)}
                          <br />
                          <span className="muted" style={{ fontSize: 11 }}>{currency(item.last_price)}원</span>
                        </>
                      ) : (
                        <>{currency(item.last_price)}원</>
                      )}
                    </td>
                    <td className={`num ${toneClass(pnl)}`}>
                      {isUS ? toUsd(pnl) : `${currency(pnl)}원`}
                    </td>
                    <td className={`num ${toneClass(pnlPctRow)}`} style={{ fontWeight: 600 }}>
                      {percent(pnlPctRow)}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="btn btn--sm"
                          title="추가 매수 (API)"
                          onClick={() => { setShowImport(false); openOrder(item, "buy"); }}
                        >
                          매수+
                        </button>
                        <button
                          type="button"
                          className="btn btn--sm btn--danger"
                          title="API 매도"
                          onClick={() => { setShowImport(false); openOrder(item, "sell"); }}
                        >
                          매도
                        </button>
                        <button
                          type="button"
                          className="btn btn--sm"
                          title="앱에서 이미 매도했으면 추적만 제거"
                          style={{ fontSize: 11, opacity: 0.75 }}
                          onClick={() => {
                            if (window.confirm(`앱에서 ${item.stock_name || item.stock_code}을(를) 이미 매도하셨나요? DB 추적에서 제거합니다.`)) {
                              void mutations.removePosition.mutateAsync({
                                stock_code: item.stock_code,
                                session: item.session as "KR" | "US",
                              }).then(() => toast.success(`${item.stock_name || item.stock_code} 추적 제거 완료`))
                                .catch((e: unknown) => toast.error(e instanceof Error ? e.message : "제거 실패"));
                            }
                          }}
                        >
                          앱매도↗
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            {tab === "ALL"
              ? t("panels.portfolio.empty")
              : `${tab === "KR" ? "국내" : "해외"} 보유종목이 없습니다.`}
            <div className="empty-state__hint">{t("panels.portfolio.emptyHint")}</div>
          </div>
        )}

        {/* 인라인 주문 패널 */}
        {orderTarget && (
          <div
            style={{
              marginTop: 12,
              padding: "12px 14px",
              background: "var(--bg-subtle)",
              border: `1px solid ${orderTarget.side === "sell" ? "var(--red-500)" : "var(--accent)"}`,
              borderRadius: 6,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 10, fontSize: 14 }}>
              {orderTarget.stock_name}
              <span className="mono" style={{ fontWeight: 400, fontSize: 12, marginLeft: 6 }}>
                ({orderTarget.stock_code} · {orderTarget.session})
              </span>
              <span style={{ marginLeft: 8 }}>
                — {orderTarget.side === "sell" ? "매도" : "추가 매수"}
              </span>
            </div>

            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              {/* 수량 입력 */}
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 13 }}>수량</span>
                <input
                  type="number"
                  className="input"
                  min={1}
                  max={orderTarget.side === "sell" ? orderTarget.held_qty : undefined}
                  value={orderQty}
                  onChange={(e) => setOrderQty(Math.max(1, Number(e.target.value)))}
                  style={{ width: 80 }}
                />
                {orderTarget.side === "sell" && (
                  <>
                    <span className="muted" style={{ fontSize: 12 }}>/ {orderTarget.held_qty}주</span>
                    <button
                      type="button"
                      className="btn btn--sm"
                      onClick={() => setOrderQty(orderTarget.held_qty)}
                    >
                      전량
                    </button>
                  </>
                )}
              </div>

              {/* 예상 금액 */}
              <div className="muted" style={{ fontSize: 13 }}>
                예상 {orderTarget.side === "sell" ? "매도" : "매수"}금액:{" "}
                <strong style={{ color: "var(--ink-1)" }}>
                  {orderTarget.session === "US"
                    ? `${toUsd(orderTarget.last_price * orderQty)} (${currency(orderTarget.last_price * orderQty)}원)`
                    : `${currency(orderTarget.last_price * orderQty)}원`}
                </strong>
              </div>

              {/* 버튼 */}
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  className={`btn btn--sm ${orderTarget.side === "sell" ? "btn--danger" : "btn--accent"}`}
                  onClick={() => void submitOrder()}
                  disabled={mutations.manualOrder.isPending}
                >
                  {mutations.manualOrder.isPending ? "처리 중..." : orderTarget.side === "sell" ? "매도 확인" : "매수 확인"}
                </button>
                <button
                  type="button"
                  className="btn btn--sm"
                  onClick={() => setOrderTarget(null)}
                >
                  취소
                </button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* 주문 내역 */}
      {portfolio.orders && portfolio.orders.length > 0 && (
        <Card title="최근 주문" eyebrow="ORDERS" style={{ marginTop: 14 }}>
          <table className="table">
            <thead>
              <tr>
                <th>종목</th>
                <th>구분</th>
                <th>세션</th>
                <th className="num">수량</th>
                <th className="num">가격</th>
                <th>상태</th>
                <th>시각</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.orders.slice(0, 20).map((o) => (
                <tr key={o.id ?? `${o.stock_code}-${o.created_at}`}>
                  <td className="mono">{o.stock_code}</td>
                  <td className={o.side === "buy" ? "positive" : "negative"}>
                    {o.side === "buy" ? "매수" : "매도"}
                  </td>
                  <td>
                    <Badge tone={o.session === "US" ? "blue" : "green"}>{o.session}</Badge>
                  </td>
                  <td className="num">{o.qty}</td>
                  <td className="num">{(o.executed_price ?? o.requested_price) ? currency((o.executed_price ?? o.requested_price)!) : "-"}</td>
                  <td>
                    <Badge tone={o.status === "filled" ? "green" : "gray"}>{o.status}</Badge>
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>
                    {o.created_at ? new Date(o.created_at).toLocaleString("ko-KR") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
};

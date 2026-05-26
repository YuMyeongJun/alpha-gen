import { Badge } from "@/components/common/Badge";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassByStatus, currency, formatCompactDateTime, shortText, toneClass } from "@/utils/format";

export interface IOrdersPanelProps {
  orders: NonNullable<IDashboardBundleRes["orders"]["orders"]>;
}

export const OrdersPanel = ({ orders }: IOrdersPanelProps) => {
  if (!orders.length) {
    return (
      <article className="panel panel-orders">
        <div className="panel-header">
          <h3>주문 내역</h3>
          <Badge>최근 주문</Badge>
        </div>
        <div className="list-stack">
          <div className="list-card">주문 이력이 없습니다.</div>
        </div>
      </article>
    );
  }

  const filledCount = orders.filter((order) => String(order.status).toLowerCase() === "filled").length;
  const rejectedCount = orders.filter((order) => String(order.status).toLowerCase() === "rejected").length;
  const realizedTotal = orders.reduce((sum, order) => sum + Number(order.realized_pnl || 0), 0);

  return (
    <article className="panel panel-orders">
      <div className="panel-header">
        <h3>주문 내역</h3>
        <Badge>최근 주문</Badge>
      </div>
      <div className="list-stack">
        <div className="list-toolbar">
          <Badge>전체 {orders.length}건</Badge>
          <Badge tone="success">체결 {filledCount}건</Badge>
          <Badge tone="danger">거절 {rejectedCount}건</Badge>
          <Badge tone={realizedTotal >= 0 ? "success" : "danger"}>
            실현손익 {realizedTotal >= 0 ? "+" : ""}
            {currency(realizedTotal)}원
          </Badge>
        </div>
        <div className="dense-table-wrap">
          <table className="dense-table">
            <thead>
              <tr>
                <th>종목</th>
                <th>구분</th>
                <th>상태</th>
                <th>가격/수량</th>
                <th>실현손익</th>
                <th>시각</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order, index) => (
                <tr key={`${order.stock_code}-${order.created_at}-${index}`}>
                  <td>
                    <div className="cell-title">{order.stock_name || order.stock_code}</div>
                    <div className="cell-sub">
                      {order.stock_code} · <span className="cell-note">{shortText(order.message || "주문 메시지 없음")}</span>
                    </div>
                  </td>
                  <td>
                    <div className="stacked-badges">
                      <span className={`side-badge ${String(order.side).toLowerCase()}`}>{String(order.side).toUpperCase()}</span>
                      <span className={`pill ${String(order.session).toLowerCase()}`}>{order.session}</span>
                    </div>
                  </td>
                  <td>
                    <Badge tone={badgeClassByStatus(order.status) as "success" | "warning" | "danger"}>{order.status}</Badge>
                  </td>
                  <td>
                    {currency(order.executed_price || order.requested_price)}원
                    <div className="cell-sub">
                      {order.qty}주 · 시도 {order.attempt_count || 0}회
                    </div>
                  </td>
                  <td className={toneClass(order.realized_pnl)}>
                    {order.realized_pnl == null ? "-" : `${currency(order.realized_pnl)}원`}
                  </td>
                  <td>{formatCompactDateTime(order.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </article>
  );
};

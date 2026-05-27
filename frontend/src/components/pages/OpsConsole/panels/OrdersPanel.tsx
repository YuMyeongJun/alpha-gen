import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, PageHeader } from "@/components/common";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IOrderRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassByStatus, currency, formatCompactDateTime } from "@/utils/format";
import {
  countOrdersToday,
  filterOrders,
  shortOrderId,
  type IOrderFilters,
  type OrderFilterSession,
  type OrderFilterSide,
  type OrderFilterStatus,
} from "@/utils/orders";

export interface IOrdersPanelProps {
  orders: IOrderRes[];
}

function orderBadgeTone(status: string): "green" | "amber" | "red" | "gray" {
  const mapped = badgeClassByStatus(status);
  if (mapped === "success") return "green";
  if (mapped === "danger") return "red";
  if (mapped === "warning") return "amber";
  return "gray";
}

const DEFAULT_FILTERS: IOrderFilters = { status: "all", side: "all", session: "all" };

export const OrdersPanel = ({ orders }: IOrdersPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const [filters, setFilters] = useState<IOrderFilters>(DEFAULT_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const todayCount = useMemo(() => countOrdersToday(orders), [orders]);
  const filtered = useMemo(() => filterOrders(orders, filters), [orders, filters]);
  const activeFilterCount = [filters.status, filters.side, filters.session].filter((v) => v !== "all").length;

  return (
    <>
      <PageHeader title={t("panels.orders.title")} subtitle={t("panels.orders.subtitle")} />

      <Card
        title={t("panels.orders.cardTitle")}
        eyebrow={t("panels.orders.eyebrow")}
        right={
          <div className="row" style={{ gap: 6 }}>
            <Badge tone="gray">{t("panels.orders.todayCount", { count: todayCount })}</Badge>
            <button type="button" className="btn btn--sm" onClick={() => setShowFilters((v) => !v)}>
              {t("common.filter")}
              {activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
            </button>
          </div>
        }
      >
        {showFilters ? (
          <div className="row" style={{ gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
            <select
              className="select"
              value={filters.status}
              onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value as OrderFilterStatus }))}
            >
              <option value="all">{t("domain.orderStatus.all")}</option>
              <option value="filled">{t("domain.orderStatus.filled")}</option>
              <option value="rejected">{t("domain.orderStatus.rejected")}</option>
              <option value="pending">{t("domain.orderStatus.pending")}</option>
            </select>
            <select
              className="select"
              value={filters.side}
              onChange={(e) => setFilters((prev) => ({ ...prev, side: e.target.value as OrderFilterSide }))}
            >
              <option value="all">{t("domain.orderSide.all")}</option>
              <option value="buy">{t("domain.orderSide.buy")}</option>
              <option value="sell">{t("domain.orderSide.sell")}</option>
            </select>
            <select
              className="select"
              value={filters.session}
              onChange={(e) => setFilters((prev) => ({ ...prev, session: e.target.value as OrderFilterSession }))}
            >
              <option value="all">{t("domain.orderSession.all")}</option>
              <option value="KR">KR</option>
              <option value="US">US</option>
            </select>
            {activeFilterCount > 0 ? (
              <button type="button" className="btn btn--sm btn--ghost" onClick={() => setFilters(DEFAULT_FILTERS)}>
                {t("common.reset")}
              </button>
            ) : null}
          </div>
        ) : null}

        {!filtered.length ? (
          <div className="empty-state">
            {orders.length ? t("panels.orders.emptyFiltered") : t("panels.orders.empty")}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.orders.colId")}</th>
                <th>{t("panels.orders.colSymbol")}</th>
                <th>{t("panels.orders.colTime")}</th>
                <th>{t("panels.orders.colCode")}</th>
                <th>{t("panels.orders.colSide")}</th>
                <th className="num">{t("panels.orders.colQty")}</th>
                <th className="num">{t("panels.orders.colPrice")}</th>
                <th>{t("panels.orders.colStatus")}</th>
                <th>{t("panels.orders.colNote")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((order, index) => (
                <tr key={order.id || `${order.stock_code}-${order.created_at}-${index}`}>
                  <td className="mono muted">{shortOrderId(order.id)}</td>
                  <td>{order.stock_name || order.stock_code}</td>
                  <td className="mono muted">{formatCompactDateTime(order.created_at)}</td>
                  <td className="mono">{order.stock_code}</td>
                  <td>
                    {String(order.side).toLowerCase() === "buy" ? (
                      <Badge tone="green">{labels.orderSide("buy")}</Badge>
                    ) : (
                      <Badge tone="red">{labels.orderSide("sell")}</Badge>
                    )}
                  </td>
                  <td className="num mono">{order.qty}</td>
                  <td className="num mono">{currency(order.executed_price || order.requested_price)}</td>
                  <td>
                    <Badge tone={orderBadgeTone(order.status)} dot>
                      {labels.orderStatus(order.status)}
                    </Badge>
                  </td>
                  <td className="muted" style={{ fontSize: 12.5 }}>
                    {order.message || order.session}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
};

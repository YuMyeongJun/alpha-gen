import type { IOrderRes } from "@/models/interface/res/IDashboardRes";

export type OrderFilterStatus = "all" | "filled" | "rejected" | "pending";
export type OrderFilterSide = "all" | "buy" | "sell";
export type OrderFilterSession = "all" | "KR" | "US";

export interface IOrderFilters {
  status: OrderFilterStatus;
  side: OrderFilterSide;
  session: OrderFilterSession;
}

export function kstDateKey(iso?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

export function countOrdersToday(orders: IOrderRes[]): number {
  const today = kstDateKey(new Date().toISOString());
  return orders.filter((order) => kstDateKey(order.created_at) === today).length;
}

export function filterOrders(orders: IOrderRes[], filters: IOrderFilters): IOrderRes[] {
  return orders.filter((order) => {
    if (filters.status !== "all" && String(order.status).toLowerCase() !== filters.status) return false;
    if (filters.side !== "all" && String(order.side).toLowerCase() !== filters.side) return false;
    if (filters.session !== "all" && String(order.session).toUpperCase() !== filters.session) return false;
    return true;
  });
}

export function shortOrderId(id?: string): string {
  if (!id) return "-";
  return id.slice(0, 8);
}

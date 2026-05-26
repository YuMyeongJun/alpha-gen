export function currency(value: number | string | null | undefined): string {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

export function percent(value: number | string | null | undefined): string {
  const numeric = Number(value || 0);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
}

export function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "없음";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function formatCompactDateTime(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelative(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return "없음";
  const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
  if (diffSec >= 0) {
    if (diffSec < 60) return `${diffSec}초 후`;
    const min = Math.floor(diffSec / 60);
    const sec = diffSec % 60;
    return `${min}분 ${sec}초 후`;
  }
  const ago = Math.abs(diffSec);
  if (ago < 60) return `${ago}초 전`;
  const min = Math.floor(ago / 60);
  const sec = ago % 60;
  return `${min}분 ${sec}초 전`;
}

export function toneClass(value: number | string | null | undefined): string {
  const numeric = Number(value || 0);
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

export function badgeClassByStatus(status?: string): string {
  const normalized = String(status || "").toLowerCase();
  if (["filled", "running", "ready", "ok"].includes(normalized)) return "success";
  if (["rejected", "error", "stopped"].includes(normalized)) return "danger";
  return "warning";
}

export function badgeClassBySeverity(severity?: string): string {
  const normalized = String(severity || "").toLowerCase();
  if (["critical", "danger"].includes(normalized)) return "danger";
  if (normalized === "warning") return "warning";
  return "success";
}

export function shortText(value: unknown, maxLength = 42): string {
  const normalized = String(value ?? "").trim();
  if (normalized.length <= maxLength) return normalized || "-";
  return `${normalized.slice(0, maxLength - 1)}…`;
}

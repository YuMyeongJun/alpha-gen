import type { TFunction } from "i18next";
import type { StagePillId } from "@/components/common/StagePills";
import type { OperatingStage } from "@/models/type/commonType";

export type SignalVerdict = "buy" | "sell" | "watch" | "skip";

export function operatingStageLabel(t: TFunction, stage?: string | null): string {
  const key = String(stage || "").toLowerCase();
  if (!key) return "-";
  const translated = t(`domain.stage.${key}`, { defaultValue: "" });
  return translated || key;
}

export function stagePillLabel(t: TFunction, pill: StagePillId): string {
  return t(`domain.stagePill.${pill}`);
}

export function orderSideLabel(t: TFunction, side?: string | null): string {
  const key = String(side || "").toLowerCase();
  if (key === "buy" || key === "sell") return t(`domain.orderSide.${key}`);
  return key || "-";
}

export function orderStatusLabel(t: TFunction, status?: string | null): string {
  const key = String(status || "").toLowerCase();
  if (key === "filled" || key === "rejected" || key === "pending") {
    return t(`domain.orderStatus.${key}`);
  }
  return key ? key.toUpperCase() : "-";
}

export function signalVerdictLabel(t: TFunction, verdict: SignalVerdict): string {
  return t(`domain.signalVerdict.${verdict}`);
}

export function workerRunningLabel(t: TFunction, running: boolean): string {
  return running ? t("domain.worker.running") : t("domain.worker.stopped");
}

export function workerStatusLabel(t: TFunction, status?: string | null): string {
  const key = String(status || "idle").toLowerCase();
  if (key === "idle" || key === "running" || key === "stopped" || key === "error") {
    return t(`domain.workerStatus.${key}`);
  }
  return key;
}

export function healthSummaryLabel(t: TFunction, summary?: string | null): string {
  const key = String(summary || "unknown").toLowerCase();
  if (key === "ready" || key === "degraded" || key === "unknown") {
    return t(`domain.health.${key}`);
  }
  return key;
}

export function auditLevelLabel(t: TFunction, severity?: string | null): string {
  const normalized = String(severity || "info").toUpperCase();
  if (normalized.includes("WARN")) return t("domain.auditLevel.warn");
  if (normalized.includes("ERROR") || normalized.includes("CRIT")) return t("domain.auditLevel.error");
  return t("domain.auditLevel.info");
}

export function stageFromPill(pill: StagePillId): OperatingStage {
  if (pill === "paper") return "paper";
  if (pill === "live") return "live_limited";
  return "shadow";
}

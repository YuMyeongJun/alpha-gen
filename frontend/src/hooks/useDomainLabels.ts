import { useTranslation } from "react-i18next";
import type { StagePillId } from "@/components/common/StagePills";
import {
  auditLevelLabel,
  healthSummaryLabel,
  operatingStageLabel,
  orderSideLabel,
  orderStatusLabel,
  signalVerdictLabel,
  stagePillLabel,
  workerRunningLabel,
  workerStatusLabel,
  type SignalVerdict,
} from "@/utils/domainLabels";

export function useDomainLabels() {
  const { t } = useTranslation();

  return {
    t,
    operatingStage: (stage?: string | null) => operatingStageLabel(t, stage),
    stagePill: (pill: StagePillId) => stagePillLabel(t, pill),
    orderSide: (side?: string | null) => orderSideLabel(t, side),
    orderStatus: (status?: string | null) => orderStatusLabel(t, status),
    signalVerdict: (verdict: SignalVerdict) => signalVerdictLabel(t, verdict),
    workerRunning: (running: boolean) => workerRunningLabel(t, running),
    workerStatus: (status?: string | null) => workerStatusLabel(t, status),
    healthSummary: (summary?: string | null) => healthSummaryLabel(t, summary),
    auditLevel: (severity?: string | null) => auditLevelLabel(t, severity),
  };
}

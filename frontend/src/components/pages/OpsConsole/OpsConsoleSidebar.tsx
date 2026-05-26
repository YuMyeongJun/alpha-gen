import { yupResolver } from "@hookform/resolvers/yup";
import { useEffect, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import * as yup from "yup";
import { Badge } from "@/components/common/Badge";
import { OpsConsoleNav } from "@/components/pages/OpsConsole/OpsConsoleNav";
import { useOpsMutations } from "@/hooks/client/safety/useSafetyMutations";
import type { IDashboardBundleRes, ISafetyPolicyRes } from "@/models/interface/res/IDashboardRes";
import type { OperatingStage } from "@/models/type/commonType";
import { formatDateTime, formatRelative } from "@/utils/format";

const STAGES: OperatingStage[] = ["mock", "paper", "shadow", "live_limited", "live_full"];

const emergencyStopSchema = yup.object({
  reason: yup.string().trim().required("긴급 정지 사유를 입력하세요.").min(2, "사유는 2자 이상이어야 합니다."),
});

const stageSchema = yup.object({
  stage: yup.string().oneOf(STAGES).required(),
});

const paperOrderSchema = yup.object({
  stock_code: yup.string().trim().required("심볼을 입력하세요."),
  session: yup.string().oneOf(["KR", "US"]).required(),
  side: yup.string().oneOf(["buy", "sell"]).required(),
  qty: yup.number().typeError("수량은 숫자여야 합니다.").integer().min(1).required(),
});

type EmergencyStopForm = yup.InferType<typeof emergencyStopSchema>;
type StageForm = yup.InferType<typeof stageSchema>;
type PaperOrderForm = yup.InferType<typeof paperOrderSchema>;

export interface IOpsConsoleSidebarProps {
  data: IDashboardBundleRes;
}

export const OpsConsoleSidebar = ({ data }: IOpsConsoleSidebarProps) => {
  const { t } = useTranslation();
  const { policy } = data.safety;
  const worker = data.system.worker;
  const mutations = useOpsMutations();

  const workerRunning = Boolean(worker.running);
  const missingConfig = data.system.diagnostics.integrations.missing_config || [];
  const modeText = data.system.config.mock_mode
    ? `Mock (${data.system.config.mock_mode_reason || "manual"})`
    : `${data.system.config.operating_stage}${data.system.config.allow_live_trading ? " · live enabled" : ""}`;

  const runAction = async (action: () => Promise<unknown>, successMessage: string) => {
    try {
      await action();
      toast.success(successMessage);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("ops.requestFailed"));
    }
  };

  const emergencyActive = Boolean(policy.emergency_stop?.enabled);

  return (
    <>
      <div className="sidebar-header">
        <div className="brand-card brand-card-compact">
          <div className="brand-mark">A</div>
          <div>
            <p className="eyebrow eyebrow-sidebar">ALPHA-GEN</p>
            <h1>Alpha-Gen</h1>
          </div>
        </div>
        <div className="badge-row badge-row-compact">
          <Badge tone={data.system.config.mock_mode ? "warning" : "success"}>{modeText}</Badge>
          <Badge tone={policy.shadow_mode ? "warning" : policy.live_orders_enabled ? "danger" : "success"}>
            {policy.stage}
          </Badge>
          <Badge tone={workerRunning ? "success" : "danger"}>
            {workerRunning ? t("sidebar.workerRunning") : t("sidebar.workerStopped")}
          </Badge>
          <Badge tone={emergencyActive ? "danger" : "success"}>
            {emergencyActive ? t("sidebar.emergencyStopOn") : t("sidebar.emergencyStopOff")}
          </Badge>
          <Badge tone={missingConfig.length ? "warning" : "success"}>
            {missingConfig.length ? t("sidebar.configIncomplete") : t("sidebar.configComplete")}
          </Badge>
        </div>
      </div>

      <OpsConsoleNav />

      <div className="sidebar-card sidebar-card-compact">
        <div className="section-title section-title-compact">
          <h2>{t("sidebar.quickActions")}</h2>
        </div>
        <div className="quick-actions-grid">
          <button
            type="button"
            className="compact-button"
            onClick={() =>
              runAction(
                () => mutations.refreshAnalysis.mutateAsync({ session: "AUTO", force_refresh: true }),
                t("sidebar.refreshAnalysisDone"),
              )
            }
          >
            {t("sidebar.refreshAnalysis")}
          </button>
          <button
            type="button"
            className="compact-button"
            onClick={() =>
              runAction(
                () => mutations.runCycle.mutateAsync({ session: "AUTO", force_refresh: false, place_orders: true }),
                t("sidebar.runCycleDone"),
              )
            }
          >
            {t("sidebar.runCycle")}
          </button>
          <button
            type="button"
            className="compact-button"
            onClick={() =>
              runAction(
                () => mutations.startWorker.mutateAsync({ interval_sec: 60, session: "AUTO", place_orders: true }),
                t("sidebar.startWorkerDone"),
              )
            }
          >
            {t("sidebar.startWorker")}
          </button>
          <button
            type="button"
            className="compact-button secondary"
            onClick={() => runAction(() => mutations.stopWorker.mutateAsync(), t("sidebar.stopWorkerDone"))}
          >
            {t("sidebar.stopWorker")}
          </button>
        </div>
      </div>

      <CollapsibleSidebarSection
        summary={`${t("sidebar.workerMonitor")} · ${workerRunning ? t("sidebar.autoRunning") : t("sidebar.idle")}`}
      >
        <WorkerMonitor worker={worker} workerRunning={workerRunning} />
      </CollapsibleSidebarSection>

      <CollapsibleSidebarSection
        summary={`${t("sidebar.safetyControls")} · ${policy.stage}${emergencyActive ? ` · ${t("sidebar.active")}` : ""}`}
      >
        <SafetyControls
          policy={policy}
          onEmergencyStop={(enabled, reason) =>
            runAction(
              () =>
                mutations.setEmergencyStop.mutateAsync({
                  enabled,
                  reason: enabled ? reason : "",
                }),
              enabled ? t("sidebar.emergencyStopEnabled") : t("sidebar.emergencyStopDisabled"),
            )
          }
          onStageSubmit={(stage) =>
            runAction(
              () => mutations.setStage.mutateAsync({ stage: stage as OperatingStage }),
              t("sidebar.stageUpdated"),
            )
          }
        />
      </CollapsibleSidebarSection>

      <CollapsibleSidebarSection summary={t("sidebar.paperOrder")}>
        <PaperOrderFormCard
          onSubmit={(values) =>
            runAction(
              () =>
                mutations.placePaperOrder.mutateAsync({
                  stock_code: values.stock_code,
                  session: values.session,
                  side: values.side as "buy" | "sell",
                  qty: Number(values.qty),
                }),
              t("sidebar.paperOrderDone"),
            )
          }
        />
      </CollapsibleSidebarSection>
    </>
  );
};

interface WorkerMonitorProps {
  worker: IDashboardBundleRes["system"]["worker"];
  workerRunning: boolean;
}

interface CollapsibleSidebarSectionProps {
  summary: string;
  children: ReactNode;
}

const CollapsibleSidebarSection = ({ summary, children }: CollapsibleSidebarSectionProps) => (
  <details className="sidebar-collapse">
    <summary>{summary}</summary>
    <div className="sidebar-collapse-body">{children}</div>
  </details>
);

const WorkerMonitor = ({ worker, workerRunning }: WorkerMonitorProps) => {
  const { t } = useTranslation();
  const lastResult = worker.last_result || {};

  return (
    <div className="sidebar-card sidebar-card-compact sidebar-card-flat">
      <div className="worker-monitor worker-monitor-grid">
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.currentStatus")}</div>
          <div className="worker-monitor-value">{workerRunning ? t("sidebar.autoRunning") : t("sidebar.idle")}</div>
          <div className="worker-monitor-note">{worker.current_status || "idle"}</div>
        </div>
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.lastRun")}</div>
          <div className="worker-monitor-value">{formatDateTime(worker.last_cycle_at)}</div>
          <div className="worker-monitor-note">{formatRelative(worker.last_cycle_at)}</div>
        </div>
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.nextRun")}</div>
          <div className="worker-monitor-value">{formatDateTime(worker.next_cycle_at)}</div>
          <div className="worker-monitor-note">{formatRelative(worker.next_cycle_at)}</div>
        </div>
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.recentCycle")}</div>
          <div className="worker-monitor-value">{worker.cycle_count || 0}{t("sidebar.cycleCount")}</div>
          <div className="worker-monitor-note">
            {t("sidebar.signals")} {lastResult.last_signal_count ?? worker.last_signal_count ?? 0}
            {t("sidebar.countUnit")} · {t("sidebar.orders")}{" "}
            {lastResult.last_order_count ?? worker.last_order_count ?? 0}
            {t("sidebar.countUnit")}
          </div>
        </div>
      </div>
    </div>
  );
};

interface SafetyControlsProps {
  policy: ISafetyPolicyRes;
  onEmergencyStop: (enabled: boolean, reason: string) => void;
  onStageSubmit: (stage: string) => void;
}

const SafetyControls = ({ policy, onEmergencyStop, onStageSubmit }: SafetyControlsProps) => {
  const { t } = useTranslation();
  const stop = policy.emergency_stop || { enabled: false };
  const limits = policy.limits || {};

  const emergencyForm = useForm<EmergencyStopForm>({
    resolver: yupResolver(emergencyStopSchema),
    defaultValues: { reason: t("sidebar.defaultStopReason") },
  });

  const stageForm = useForm<StageForm>({
    resolver: yupResolver(stageSchema),
    defaultValues: { stage: policy.stage || "paper" },
  });

  useEffect(() => {
    stageForm.reset({ stage: policy.stage || "paper" });
  }, [policy.stage, stageForm]);

  return (
    <div className="sidebar-card sidebar-card-compact sidebar-card-flat">
      <div className="worker-monitor worker-monitor-grid">
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.operatingStage")}</div>
          <div className="worker-monitor-value">{policy.stage}</div>
          <div className="worker-monitor-note">
            {t("sidebar.autoOrders")} {policy.auto_orders_enabled ? t("sidebar.enabled") : t("sidebar.disabled")} ·{" "}
            {t("sidebar.liveTrading")} {policy.live_orders_enabled ? t("sidebar.enabled") : t("sidebar.disabled")}
          </div>
        </div>
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.emergencyStop")}</div>
          <div className={`worker-monitor-value ${stop.enabled ? "negative" : "positive"}`}>
            {stop.enabled ? t("sidebar.active") : t("sidebar.inactive")}
          </div>
          <div className="worker-monitor-note">{stop.reason || t("sidebar.normalOperation")}</div>
        </div>
        <div className="worker-monitor-card">
          <div className="worker-monitor-label">{t("sidebar.orderLimits")}</div>
          <div className="worker-monitor-value">
            {limits.live_max_orders_per_day ?? "-"}
            {t("sidebar.perDay")}
          </div>
          <div className="worker-monitor-note">
            {t("sidebar.signalStaleness")} {limits.signal_staleness_sec ?? "-"}
            {t("sidebar.seconds")} · {t("sidebar.quoteStaleness")} {limits.quote_staleness_sec ?? "-"}
            {t("sidebar.seconds")}
          </div>
        </div>
      </div>
      <form onSubmit={emergencyForm.handleSubmit((values) => onEmergencyStop(true, values.reason))}>
        <label>
          {t("sidebar.stopReason")}
          <input {...emergencyForm.register("reason")} />
        </label>
        {emergencyForm.formState.errors.reason ? (
          <p className="form-error">{emergencyForm.formState.errors.reason.message}</p>
        ) : null}
        <button type="submit" className="danger-button">
          {t("sidebar.enableEmergencyStop")}
        </button>
      </form>
      <button type="button" className="secondary" onClick={() => onEmergencyStop(false, "")}>
        {t("sidebar.disableEmergencyStop")}
      </button>
      <form onSubmit={stageForm.handleSubmit((values) => onStageSubmit(values.stage))}>
        <label>
          {t("sidebar.operatingStage")}
          <select {...stageForm.register("stage")}>
            {STAGES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">{t("sidebar.applyStage")}</button>
      </form>
    </div>
  );
};

interface PaperOrderFormCardProps {
  onSubmit: (values: PaperOrderForm) => void;
}

const PaperOrderFormCard = ({ onSubmit }: PaperOrderFormCardProps) => {
  const { t } = useTranslation();
  const form = useForm<PaperOrderForm>({
    resolver: yupResolver(paperOrderSchema),
    defaultValues: {
      stock_code: "005930",
      session: "KR",
      side: "buy",
      qty: 1,
    },
  });

  return (
    <div className="sidebar-card sidebar-card-compact sidebar-card-flat">
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <label>
          {t("sidebar.symbol")}
          <input {...form.register("stock_code")} />
        </label>
        {form.formState.errors.stock_code ? (
          <p className="form-error">{form.formState.errors.stock_code.message}</p>
        ) : null}
        <label>
          {t("sidebar.session")}
          <select {...form.register("session")}>
            <option value="KR">KR</option>
            <option value="US">US</option>
          </select>
        </label>
        <label>
          {t("sidebar.side")}
          <select {...form.register("side")}>
            <option value="buy">BUY</option>
            <option value="sell">SELL</option>
          </select>
        </label>
        <label>
          {t("sidebar.qty")}
          <input type="number" min={1} {...form.register("qty", { valueAsNumber: true })} />
        </label>
        {form.formState.errors.qty ? <p className="form-error">{form.formState.errors.qty.message}</p> : null}
        <button type="submit">{t("sidebar.submitPaperOrder")}</button>
      </form>
    </div>
  );
};

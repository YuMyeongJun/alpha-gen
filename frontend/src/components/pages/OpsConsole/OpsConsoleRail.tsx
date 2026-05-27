import { yupResolver } from "@hookform/resolvers/yup";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import * as yup from "yup";
import { Badge, ConfirmDialog, Icon, StagePills, pillToStage, stageToPill } from "@/components/common";
import { useOpsMutations } from "@/hooks/client/safety/useSafetyMutations";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import type { OperatingStage } from "@/models/type/commonType";
import { formatDateTime, formatRelative } from "@/utils/format";

const STAGES: OperatingStage[] = ["mock", "paper", "shadow", "live_limited", "live_full"];

type EmergencyStopForm = { reason: string };
type PaperOrderForm = { stock_code: string; session: "KR" | "US"; side: "buy" | "sell"; qty: number };

export interface IOpsConsoleRailProps {
  data: IDashboardBundleRes;
}

export const OpsConsoleRail = ({ data }: IOpsConsoleRailProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const { policy } = data.safety;
  const worker = data.system.worker;
  const mutations = useOpsMutations();
  const workerRunning = Boolean(worker.running);
  const emergencyActive = Boolean(policy.emergency_stop?.enabled);
  const lastResult = worker.last_result || {};

  const emergencyStopSchema = useMemo(
    () =>
      yup.object({
        reason: yup
          .string()
          .trim()
          .required(t("sidebar.validation.stopReasonRequired"))
          .min(2, t("sidebar.validation.stopReasonMin")),
      }),
    [t],
  );

  const paperOrderSchema = useMemo(
    () =>
      yup.object({
        stock_code: yup.string().trim().required(t("sidebar.validation.symbolRequired")),
        session: yup.string().oneOf(["KR", "US"]).required(),
        side: yup.string().oneOf(["buy", "sell"]).required(),
        qty: yup.number().typeError(t("sidebar.validation.qtyNumber")).integer().min(1).required(),
      }),
    [t],
  );

  const runAction = async (action: () => Promise<unknown>, successMessage: string) => {
    try {
      await action();
      toast.success(successMessage);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("ops.requestFailed"));
    }
  };

  const emergencyForm = useForm<EmergencyStopForm>({
    resolver: yupResolver(emergencyStopSchema),
    defaultValues: { reason: t("sidebar.defaultStopReason") },
  });

  const paperForm = useForm<PaperOrderForm>({
    resolver: yupResolver(paperOrderSchema),
    defaultValues: { stock_code: "005930", session: "KR", side: "buy", qty: 1 },
  });

  const stagePill = stageToPill(policy.stage || "paper");
  const limits = policy.limits || {};
  const usage = policy.usage;
  const [estopConfirmOpen, setEstopConfirmOpen] = useState(false);

  const submitEmergencyStop = emergencyForm.handleSubmit((values) => {
    setEstopConfirmOpen(false);
    void runAction(
      () => mutations.setEmergencyStop.mutateAsync({ enabled: true, reason: values.reason }),
      t("sidebar.emergencyStopEnabled"),
    );
  });

  return (
    <aside className="rail">
      <div className="rail-card">
        <div className="rail-card__head">
          <div className="rail-card__title">{t("sidebar.quickActions")}</div>
          <span className="kbd">Q</span>
        </div>
        <div className="grid-2" style={{ gap: 8 }}>
          <button
            type="button"
            className="btn"
            disabled={mutations.refreshAnalysis.isPending}
            onClick={() =>
              runAction(
                () => mutations.refreshAnalysis.mutateAsync({ session: "AUTO", force_refresh: true }),
                t("sidebar.refreshAnalysisDone"),
              )
            }
          >
            <Icon name="refresh" size={14} className={mutations.refreshAnalysis.isPending ? "spinning" : ""} />
            {t("sidebar.refreshAnalysis")}
          </button>
          <button
            type="button"
            className="btn"
            disabled={mutations.runCycle.isPending}
            onClick={() =>
              runAction(
                () => mutations.runCycle.mutateAsync({ session: "AUTO", force_refresh: false, place_orders: true }),
                t("sidebar.runCycleDone"),
              )
            }
          >
            <Icon name="bolt" size={14} />
            {mutations.runCycle.isPending ? "..." : t("sidebar.runCycle")}
          </button>
          <button
            type="button"
            className={`btn${workerRunning ? "" : " btn--primary"}`}
            disabled={workerRunning || mutations.startWorker.isPending}
            onClick={() =>
              runAction(
                () => mutations.startWorker.mutateAsync({ interval_sec: 60, session: "AUTO", place_orders: true }),
                t("sidebar.startWorkerDone"),
              )
            }
          >
            <Icon name="play" size={12} className={mutations.startWorker.isPending ? "spinning" : ""} />
            {t("sidebar.startWorker")}
          </button>
          <button
            type="button"
            className="btn"
            disabled={!workerRunning || mutations.stopWorker.isPending}
            onClick={() => runAction(() => mutations.stopWorker.mutateAsync(), t("sidebar.stopWorkerDone"))}
          >
            <Icon name="pause" size={12} />
            {mutations.stopWorker.isPending ? "..." : t("sidebar.stopWorker")}
          </button>
        </div>
      </div>

      <div className="rail-card">
        <div className="rail-card__head">
          <div className="rail-card__title">{t("sidebar.workerMonitor")}</div>
          <Badge tone="gray" dot>
            {workerRunning ? t("sidebar.autoRunning") : t("sidebar.idle")}
          </Badge>
        </div>
        <dl className="kv">
          <dt>{t("sidebar.currentStatus")}</dt>
          <dd>{labels.workerStatus(worker.current_status)}</dd>
          <dt>{t("sidebar.lastRun")}</dt>
          <dd>
            {formatDateTime(worker.last_cycle_at)} · <span className="muted">{formatRelative(worker.last_cycle_at)}</span>
          </dd>
          <dt>{t("sidebar.nextRun")}</dt>
          <dd>{formatDateTime(worker.next_cycle_at)}</dd>
          <dt>{t("sidebar.recentCycle")}</dt>
          <dd>
            {worker.cycle_count || 0}
            {t("sidebar.cycleCount")} · {t("sidebar.signals")}{" "}
            {lastResult.last_signal_count ?? worker.last_signal_count ?? 0}
            {t("sidebar.countUnit")}
          </dd>
        </dl>
      </div>

      <div className="rail-card">
        <div className="rail-card__head">
          <div className="rail-card__title">{t("sidebar.safetyControls")}</div>
          {emergencyActive ? (
            <Badge tone="red" dot>
              {t("sidebar.emergencyStopOn")}
            </Badge>
          ) : (
            <Badge tone="green" dot>
              {t("sidebar.emergencyStopOff")}
            </Badge>
          )}
        </div>

        <div className="field" style={{ marginBottom: 12 }}>
          <span className="field__label">{t("sidebar.operatingStage")}</span>
          <StagePills
            value={stagePill}
            onChange={(pill) =>
              runAction(
                () => mutations.setStage.mutateAsync({ stage: pillToStage(pill) }),
                t("sidebar.stageUpdated"),
              )
            }
          />
          <select
            className="select"
            style={{ marginTop: 8, width: "100%" }}
            value={policy.stage}
            disabled={mutations.setStage.isPending}
            onChange={(e) =>
              runAction(
                () => mutations.setStage.mutateAsync({ stage: e.target.value as OperatingStage }),
                t("sidebar.stageUpdated"),
              )
            }
          >
            {STAGES.map((item) => (
              <option key={item} value={item}>
                {labels.operatingStage(item)}
              </option>
            ))}
          </select>
        </div>

        <div className="grid-2" style={{ gap: 8, marginBottom: 10 }}>
          <div style={{ background: "var(--bg-subtle)", padding: "10px 12px", borderRadius: 8 }}>
            <div className="muted" style={{ fontSize: 11.5 }}>
              {t("sidebar.orderLimits")}
            </div>
            <div style={{ fontWeight: 550, fontSize: 14 }}>
              {usage?.orders_today != null && limits.live_max_orders_per_day != null
                ? `${usage.orders_today}/${limits.live_max_orders_per_day}`
                : limits.live_max_orders_per_day ?? "-"}
              {t("sidebar.perDay")}
            </div>
            <div className="muted" style={{ fontSize: 11.5 }}>
              {t("sidebar.signalStaleness")} {limits.signal_staleness_sec ?? "-"}
              {t("sidebar.seconds")}
            </div>
          </div>
          <div style={{ background: "var(--bg-subtle)", padding: "10px 12px", borderRadius: 8 }}>
            <div className="muted" style={{ fontSize: 11.5 }}>
              {t("sidebar.risk")}
            </div>
            <div style={{ fontWeight: 550, fontSize: 14 }}>
              {limits.max_daily_loss_pct != null
                ? `${Number(limits.max_daily_loss_pct).toFixed(1)}%`
                : data.portfolio.risk?.drawdown_pct != null
                  ? `${Number(data.portfolio.risk.drawdown_pct).toFixed(2)}%`
                  : "-"}
            </div>
            <div className="muted" style={{ fontSize: 11.5 }}>
              {data.portfolio.risk?.sleep_mode ? t("domain.risk.sleepMode") : t("domain.risk.dailyLossLimit")}
            </div>
          </div>
        </div>

        <form
          className="field"
          style={{ marginBottom: 10 }}
          onSubmit={(event) => {
            event.preventDefault();
            void emergencyForm.handleSubmit(() => setEstopConfirmOpen(true))();
          }}
        >
          <span className="field__label">{t("sidebar.stopReason")}</span>
          <input className="input" {...emergencyForm.register("reason")} />
          {emergencyForm.formState.errors.reason ? (
            <p className="form-error">{emergencyForm.formState.errors.reason.message}</p>
          ) : null}
          {emergencyActive ? (
            <button
              type="button"
              className="btn btn--block"
              style={{ marginTop: 8 }}
              disabled={mutations.setEmergencyStop.isPending}
              onClick={() =>
                runAction(
                  () => mutations.setEmergencyStop.mutateAsync({ enabled: false, reason: "" }),
                  t("sidebar.emergencyStopDisabled"),
                )
              }
            >
              {mutations.setEmergencyStop.isPending ? "..." : t("sidebar.disableEmergencyStop")}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--danger btn--block"
              style={{ marginTop: 8 }}
              disabled={mutations.setEmergencyStop.isPending}
              onClick={() => void emergencyForm.handleSubmit(() => setEstopConfirmOpen(true))()}
            >
              <Icon name="warn" size={14} />
              {t("sidebar.enableEmergencyStop")}
            </button>
          )}
        </form>
        <ConfirmDialog
          open={estopConfirmOpen}
          title={t("sidebar.estopConfirmTitle")}
          body={t("sidebar.estopConfirmBody")}
          danger
          confirmText={t("sidebar.enableEmergencyStop")}
          onCancel={() => setEstopConfirmOpen(false)}
          onConfirm={() => void submitEmergencyStop()}
        />
      </div>

      <div className="rail-card">
        <div className="rail-card__head">
          <div className="rail-card__title">{t("sidebar.paperOrder")}</div>
          <Badge tone="blue" dot>
            {labels.stagePill(stagePill)}
          </Badge>
        </div>
        <form
          onSubmit={paperForm.handleSubmit((values) =>
            runAction(
              () =>
                mutations.placePaperOrder.mutateAsync({
                  stock_code: values.stock_code,
                  session: values.session,
                  side: values.side as "buy" | "sell",
                  qty: Number(values.qty),
                }),
              t("sidebar.paperOrderDone"),
            ),
          )}
        >
          <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
            <div className="field">
              <span className="field__label">{t("sidebar.symbol")}</span>
              <input className="input" {...paperForm.register("stock_code")} />
            </div>
            <div className="field">
              <span className="field__label">{t("sidebar.session")}</span>
              <select className="select" {...paperForm.register("session")}>
                <option value="KR">KR</option>
                <option value="US">US</option>
              </select>
            </div>
            <div className="field">
              <span className="field__label">{t("sidebar.side")}</span>
              <select className="select" {...paperForm.register("side")}>
                <option value="buy">{labels.orderSide("buy")}</option>
                <option value="sell">{labels.orderSide("sell")}</option>
              </select>
            </div>
            <div className="field">
              <span className="field__label">{t("sidebar.qty")}</span>
              <input className="input" type="number" min={1} {...paperForm.register("qty", { valueAsNumber: true })} />
            </div>
          </div>
          <button type="submit" className="btn btn--accent btn--block">
            {t("sidebar.submitPaperOrder")}
          </button>
        </form>
      </div>
    </aside>
  );
};

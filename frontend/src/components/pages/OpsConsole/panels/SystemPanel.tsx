import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import { Badge, Card, ConfirmDialog, Icon, PageHeader } from "@/components/common";
import { useSystemMutations } from "@/hooks/client/system/useSystemMutations";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IDashboardBundleRes, ISafetyPolicyRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassByStatus, formatDateTime, formatRelative } from "@/utils/format";

export interface ISystemPanelProps {
  system: IDashboardBundleRes["system"];
  policy: ISafetyPolicyRes;
}

function healthTone(summary: string): "green" | "amber" | "red" | "gray" {
  const mapped = badgeClassByStatus(summary);
  if (mapped === "success") return "green";
  if (mapped === "danger") return "red";
  return "amber";
}

function formatBytes(bytes?: number): string {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

type DangerAction = "cache" | "token" | "db" | null;

export const SystemPanel = ({ system, policy }: ISystemPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const diagnostics = system.diagnostics;
  const summary = diagnostics.summary || "unknown";
  const env = diagnostics.environment || {};
  const storage = diagnostics.storage || {};
  const integrations = diagnostics.integrations || {};
  const kisToken = integrations.kis_token || {};
  const packages = diagnostics.packages || {};
  const packageOk = Object.values(packages).filter((p) => p.ok).length;
  const packageTotal = Object.keys(packages).length;
  const mutations = useSystemMutations();
  const [dangerAction, setDangerAction] = useState<DangerAction>(null);
  const [adminReason, setAdminReason] = useState(t("common.operatorConfirm"));

  const runAdmin = async (action: DangerAction) => {
    if (!action) return;
    const payload = { confirm: true, reason: adminReason.trim() || t("common.operatorConfirm") };
    try {
      if (action === "cache") await mutations.clearCache.mutateAsync(payload);
      if (action === "token") await mutations.refreshKisToken.mutateAsync(payload);
      if (action === "db") await mutations.resetDatabase.mutateAsync(payload);
      toast.success(t("common.requestDone"));
      setDangerAction(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("common.requestFailed"));
    }
  };

  const syncBroker = async () => {
    try {
      await mutations.syncBroker.mutateAsync("KR");
      toast.success(t("common.syncDone"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("common.syncFailed"));
    }
  };

  const dangerCopy: Record<Exclude<DangerAction, null>, { title: string; body: string; danger?: boolean }> = {
    cache: {
      title: t("panels.system.confirmCacheTitle"),
      body: t("panels.system.confirmCacheBody"),
    },
    token: {
      title: t("panels.system.confirmTokenTitle"),
      body: t("panels.system.confirmTokenBody"),
    },
    db: {
      title: t("panels.system.confirmDbTitle"),
      body: t("panels.system.confirmDbBody"),
      danger: true,
    },
  };

  return (
    <>
      <PageHeader title={t("panels.system.title")} subtitle={t("panels.system.subtitle")} />

      <div className="grid-2" style={{ marginBottom: 14 }}>
        <Card title={t("panels.system.runtimeTitle")} eyebrow={t("panels.system.runtimeEyebrow")}>
          <dl className="kv">
            <dt>Python</dt>
            <dd className="mono">{env.python || "-"}</dd>
            <dt>FastAPI</dt>
            <dd>
              {t("common.healthy")} · <Badge tone={healthTone(summary)} dot>{labels.healthSummary(summary)}</Badge>
            </dd>
            <dt>DB</dt>
            <dd className="mono">
              {storage.db_path || system.config.db_path || "-"} · {formatBytes(storage.db_size_bytes)}
            </dd>
            <dt>{t("panels.system.operatingStage")}</dt>
            <dd>{labels.operatingStage(policy.stage)}</dd>
            <dt>{t("panels.system.worker")}</dt>
            <dd>{labels.workerRunning(system.worker.running)}</dd>
            <dt>{t("panels.system.nextRun")}</dt>
            <dd>{formatRelative(system.worker.next_cycle_at)}</dd>
          </dl>
        </Card>
        <Card
          title={t("panels.system.adaptersTitle")}
          eyebrow={t("panels.system.adaptersEyebrow")}
          right={
            <button
              type="button"
              className="btn btn--sm"
              disabled={mutations.syncBroker.isPending}
              onClick={() => void syncBroker()}
            >
              <Icon name="refresh" size={12} className={mutations.syncBroker.isPending ? "spinning" : ""} />
              {t("panels.system.syncPositions")}
            </button>
          }
        >
          <dl className="kv">
            <dt>KIS</dt>
            <dd>{integrations.kis_configured ? t("common.configured") : t("common.notConfigured")}</dd>
            <dt>Claude</dt>
            <dd>{integrations.claude_configured ? t("common.configured") : t("common.notConfigured")}</dd>
            <dt>{t("panels.system.kisToken")}</dt>
            <dd>
              {kisToken.cached ? (
                <Badge tone="green" dot>
                  {t("common.cached")}
                </Badge>
              ) : (
                <Badge tone="gray">{t("common.none")}</Badge>
              )}
              {kisToken.expires_at ? (
                <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                  {t("common.expires")} {formatDateTime(kisToken.expires_at)}
                </span>
              ) : null}
            </dd>
            <dt>{t("panels.system.packages")}</dt>
            <dd>{packageTotal ? t("common.packagesOk", { ok: packageOk, total: packageTotal }) : "-"}</dd>
            <dt>{t("panels.system.mockMode")}</dt>
            <dd>{system.config.mock_mode ? t("common.active") : t("common.inactive")}</dd>
            <dt>{t("panels.system.missingConfig")}</dt>
            <dd>{(integrations.missing_config || []).join(", ") || t("common.none")}</dd>
          </dl>
        </Card>
      </div>

      <Card title={t("panels.system.dangerTitle")} eyebrow={t("panels.system.dangerEyebrow")}>
        <p className="muted" style={{ marginTop: 0 }}>
          {t("panels.system.dangerNote")}
        </p>
        <div className="field" style={{ maxWidth: 420, marginBottom: 12 }}>
          <span className="field__label">{t("panels.system.reasonLabel")}</span>
          <input className="input" value={adminReason} onChange={(e) => setAdminReason(e.target.value)} />
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button
            type="button"
            className="btn"
            disabled={mutations.clearCache.isPending || !!dangerAction}
            onClick={() => setDangerAction("cache")}
          >
            {mutations.clearCache.isPending ? <Icon name="refresh" size={13} className="spinning" /> : null}
            {t("panels.system.clearCache")}
          </button>
          <button
            type="button"
            className="btn"
            disabled={mutations.refreshKisToken.isPending || !!dangerAction}
            onClick={() => setDangerAction("token")}
          >
            {mutations.refreshKisToken.isPending ? <Icon name="refresh" size={13} className="spinning" /> : null}
            {t("panels.system.refreshToken")}
          </button>
          <button
            type="button"
            className="btn btn--danger"
            disabled={mutations.resetDatabase.isPending || !!dangerAction}
            onClick={() => setDangerAction("db")}
          >
            {t("panels.system.resetDb")}
          </button>
        </div>
        <details className="details-card">
          <summary>{t("panels.system.diagnosticsJson")}</summary>
          <pre className="json-view">{JSON.stringify(system, null, 2)}</pre>
        </details>
      </Card>

      {dangerAction ? (
        <ConfirmDialog
          open
          title={dangerCopy[dangerAction].title}
          body={dangerCopy[dangerAction].body}
          danger={dangerCopy[dangerAction].danger}
          confirmText={t("common.execute")}
          onCancel={() => setDangerAction(null)}
          onConfirm={() => void runAdmin(dangerAction)}
        />
      ) : null}
    </>
  );
};

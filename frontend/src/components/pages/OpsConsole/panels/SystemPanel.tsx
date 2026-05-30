import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import { Badge, Card, ConfirmDialog, Icon, PageHeader } from "@/components/common";
import { useSystemMutations } from "@/hooks/client/system/useSystemMutations";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IDashboardBundleRes, ISafetyPolicyRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassByStatus, formatDateTime, formatRelative } from "@/utils/format";
import apiClient from "@/modules/apiClient";

type ImportForm = { stock_code: string; session: "KR" | "US"; qty: number; avg_price: number; stock_name: string };

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

type DangerAction = "cache" | "token" | "db" | "equity" | null;

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

  const { data: claudeUsage } = useQuery({
    queryKey: ["claude-usage"],
    queryFn: () => apiClient.get("/api/system/claude/usage").then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  const [adminReason, setAdminReason] = useState(t("common.operatorConfirm"));
  const importForm = useForm<ImportForm>({
    defaultValues: { stock_code: "", session: "KR", qty: 1, avg_price: 0, stock_name: "" },
  });

  const runAdmin = async (action: DangerAction) => {
    if (!action) return;
    const payload = { confirm: true, reason: adminReason.trim() || t("common.operatorConfirm") };
    try {
      if (action === "cache") await mutations.clearCache.mutateAsync(payload);
      if (action === "token") await mutations.refreshKisToken.mutateAsync(payload);
      if (action === "db") await mutations.resetDatabase.mutateAsync(payload);
      if (action === "equity") await mutations.clearEquity.mutateAsync(payload);
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
    equity: {
      title: "자산 추이 기록 초기화",
      body: "모의 거래 시작 시 생성된 가라 데이터를 포함, 차트에 표시되는 자산 추이 기록 전체를 삭제합니다. 실제 잔고·포지션은 영향 없습니다.",
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

      {/* 수동 포지션 등록 */}
      <Card title="외부 포지션 등록" eyebrow="IMPORT POSITION" style={{ marginBottom: 14 }}>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          한투 앱 등 외부에서 직접 매수한 포지션을 시스템에 등록합니다.
        </p>
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
              toast.success(`${values.stock_code} ${values.qty}주 등록 완료`);
              importForm.reset({ stock_code: "", session: "KR", qty: 1, avg_price: 0, stock_name: "" });
            } catch (error) {
              toast.error(error instanceof Error ? error.message : "등록 실패");
            }
          })}
        >
          <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
            <div className="field">
              <span className="field__label">종목코드</span>
              <input className="input" placeholder="005930 / AAPL" {...importForm.register("stock_code", { required: true })} />
            </div>
            <div className="field">
              <span className="field__label">종목명 (선택)</span>
              <input className="input" placeholder="자동인식됩니다" {...importForm.register("stock_name")} />
            </div>
            <div className="field">
              <span className="field__label">세션</span>
              <select className="select" {...importForm.register("session")}>
                <option value="KR">KR (국내)</option>
                <option value="US">US (미국)</option>
              </select>
            </div>
            <div className="field">
              <span className="field__label">수량 (주)</span>
              <input className="input" type="number" min={1} {...importForm.register("qty", { valueAsNumber: true, min: 1 })} />
            </div>
            <div className="field" style={{ gridColumn: "1/-1" }}>
              <span className="field__label">평균 매입가 (원)</span>
              <input className="input" type="number" min={1} {...importForm.register("avg_price", { valueAsNumber: true, min: 1 })} />
            </div>
          </div>
          <button
            type="submit"
            className="btn btn--accent"
            disabled={mutations.importPosition.isPending}
          >
            {mutations.importPosition.isPending ? <Icon name="refresh" size={13} className="spinning" /> : null}
            포지션 등록
          </button>
        </form>
      </Card>

      {/* 리스크 기준 재설정 */}
      <Card title="리스크 기준 설정" eyebrow="RISK CAPITAL" style={{ marginBottom: 14 }}>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          시스템의 드로우다운 기준이 실제 투자 자본과 다를 때(예: 페이퍼 초기값 1000만원으로 고정) 현재 총자산을 새로운 기준으로 재설정합니다.
          휴면 모드도 함께 해제됩니다.
        </p>
        <button
          type="button"
          className="btn btn--accent"
          disabled={mutations.resetCapital.isPending}
          onClick={async () => {
            try {
              await mutations.resetCapital.mutateAsync();
              toast.success("기준 자본 재설정 완료 — 드로우다운 기준이 현재 총자산으로 초기화되었습니다.");
            } catch (error) {
              toast.error(error instanceof Error ? error.message : "재설정 실패");
            }
          }}
        >
          {mutations.resetCapital.isPending ? <Icon name="refresh" size={13} className="spinning" /> : null}
          현재 자산을 리스크 기준으로 재설정
        </button>
      </Card>

      {/* Claude API 비용 모니터링 */}
      <Card title="Claude API 비용" eyebrow="AI COST MONITOR" style={{ marginBottom: 14 }}>
        {!claudeUsage ? (
          <div className="muted" style={{ padding: "8px 0" }}>불러오는 중…</div>
        ) : (
          <>
            <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
              <dl className="kv">
                <dt>오늘 API 비용</dt>
                <dd>
                  <b>${((claudeUsage.today?.cost_usd ?? 0)).toFixed(4)}</b>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>
                    ({claudeUsage.today?.calls ?? 0}회 호출)
                  </span>
                </dd>
                <dt>월 예상 비용</dt>
                <dd>
                  <b>${(claudeUsage.monthly_estimate_usd ?? 0).toFixed(2)}</b>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>
                    ≈ {Math.round((claudeUsage.monthly_estimate_usd ?? 0) * 1350).toLocaleString()}원
                  </span>
                </dd>
              </dl>
              <dl className="kv">
                <dt>세션 누적 비용</dt>
                <dd>${((claudeUsage.session?.cost_usd ?? 0)).toFixed(4)}</dd>
                <dt>세션 호출 수</dt>
                <dd>{claudeUsage.session?.calls ?? 0}회</dd>
                <dt>알림 임계값</dt>
                <dd className="muted">${claudeUsage.alert_threshold_usd ?? 1.0} / 일</dd>
              </dl>
            </div>
            {(claudeUsage.history ?? []).length > 1 && (
              <details style={{ marginTop: 6 }}>
                <summary className="muted" style={{ cursor: "pointer", fontSize: 12 }}>최근 사용 이력</summary>
                <table className="table" style={{ marginTop: 6 }}>
                  <thead>
                    <tr><th>날짜</th><th>비용(USD)</th><th>호출</th><th>입력 토큰</th><th>출력 토큰</th></tr>
                  </thead>
                  <tbody>
                    {[...(claudeUsage.history ?? [])].reverse().slice(0, 7).map((d: Record<string, unknown>) => (
                      <tr key={String(d.date)}>
                        <td className="mono muted">{String(d.date)}</td>
                        <td><b>${Number(d.cost_usd).toFixed(4)}</b></td>
                        <td>{String(d.calls)}</td>
                        <td className="muted">{Number(d.input_tokens).toLocaleString()}</td>
                        <td className="muted">{Number(d.output_tokens).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
            <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>
              💡 크레딧 소진 방지: Anthropic 콘솔 → Billing → <b>Auto top-up</b> 활성화 권장
            </p>
          </>
        )}
      </Card>

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
            className="btn"
            disabled={mutations.clearEquity.isPending || !!dangerAction}
            onClick={() => setDangerAction("equity")}
          >
            차트 기록 초기화
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

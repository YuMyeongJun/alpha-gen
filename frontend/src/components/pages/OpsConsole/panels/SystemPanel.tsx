import { Badge } from "@/components/common/Badge";
import type { IDashboardBundleRes, ISafetyPolicyRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassByStatus, formatRelative } from "@/utils/format";

export interface ISystemPanelProps {
  system: IDashboardBundleRes["system"];
  policy: ISafetyPolicyRes;
}

export const SystemPanel = ({ system, policy }: ISystemPanelProps) => {
  const modeText = system.config.mock_mode
    ? `Mock (${system.config.mock_mode_reason || "manual"})`
    : `${system.config.operating_stage}${system.config.allow_live_trading ? " · live enabled" : ""}`;

  return (
    <article className="panel panel-wide">
      <div className="panel-header">
        <h3>시스템 상태</h3>
        <Badge tone={badgeClassByStatus(system.diagnostics.summary) as "success" | "warning" | "danger"}>
          {system.diagnostics.summary}
        </Badge>
      </div>
      <div className="system-panel">
        <div className="system-grid">
          <div className="system-card">
            <span>실행 모드</span>
            <strong>{modeText}</strong>
          </div>
          <div className="system-card">
            <span>의존성 상태</span>
            <strong>{system.diagnostics.summary}</strong>
          </div>
          <div className="system-card">
            <span>최근 실행 결과</span>
            <strong>{system.worker.last_summary || "아직 없음"}</strong>
          </div>
          <div className="system-card">
            <span>다음 실행 예정</span>
            <strong>{formatRelative(system.worker.next_cycle_at)}</strong>
          </div>
          <div className="system-card">
            <span>운영 단계</span>
            <strong>{policy.stage}</strong>
          </div>
          <div className="system-card">
            <span>긴급 정지</span>
            <strong>{policy.emergency_stop?.enabled ? "활성" : "해제"}</strong>
          </div>
        </div>
        <details className="details-card">
          <summary>진단 상세 JSON 보기</summary>
          <pre className="json-view">{JSON.stringify(system, null, 2)}</pre>
        </details>
      </div>
    </article>
  );
};

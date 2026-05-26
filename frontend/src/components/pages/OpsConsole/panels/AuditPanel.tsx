import { Badge } from "@/components/common/Badge";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassBySeverity, formatCompactDateTime } from "@/utils/format";

export interface IAuditPanelProps {
  events: NonNullable<IDashboardBundleRes["audit"]["events"]>;
}

export const AuditPanel = ({ events }: IAuditPanelProps) => (
  <article className="panel panel-audit">
    <div className="panel-header">
      <h3>감사 이벤트</h3>
      <Badge>최근 이벤트</Badge>
    </div>
    <div className="list-stack">
      {!events.length ? (
        <div className="list-card">감사 이벤트가 아직 없습니다.</div>
      ) : (
        <div className="audit-list">
          {events.map((event, index) => (
            <div key={`${event.event_type}-${event.created_at}-${index}`} className={`audit-card ${String(event.severity || "info").toLowerCase()}`}>
              <div className="audit-top">
                <div>
                  <div className="audit-title">{event.event_type}</div>
                  <div className="audit-meta">
                    {formatCompactDateTime(event.created_at)} · {event.scope || "-"}
                    {event.session ? ` · ${event.session}` : ""}
                  </div>
                </div>
                <Badge tone={badgeClassBySeverity(event.severity) as "success" | "warning" | "danger"}>
                  {event.severity || "info"}
                </Badge>
              </div>
              <div className="audit-message">{event.message || "-"}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  </article>
);

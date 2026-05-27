import { useTranslation } from "react-i18next";
import { Badge, Card, PageHeader } from "@/components/common";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IAuditEventRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassBySeverity, formatCompactDateTime } from "@/utils/format";

export interface IAuditPanelProps {
  events: IAuditEventRes[];
}

function auditTone(severity?: string): "green" | "amber" | "red" | "gray" {
  const mapped = badgeClassBySeverity(severity);
  if (mapped === "danger") return "red";
  if (mapped === "warning") return "amber";
  return "gray";
}

export const AuditPanel = ({ events }: IAuditPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();

  return (
    <>
      <PageHeader title={t("panels.audit.title")} subtitle={t("panels.audit.subtitle")} />

      <Card>
        {!events.length ? (
          <div className="empty-state">{t("panels.audit.empty")}</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("panels.audit.colTime")}</th>
                <th style={{ width: 90 }}>{t("panels.audit.colLevel")}</th>
                <th style={{ width: 90 }}>{t("panels.audit.colSource")}</th>
                <th>{t("panels.audit.colMessage")}</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr key={`${event.event_type}-${event.created_at}-${index}`}>
                  <td className="mono muted">{formatCompactDateTime(event.created_at)}</td>
                  <td>
                    <Badge tone={auditTone(event.severity)} dot>
                      {labels.auditLevel(event.severity)}
                    </Badge>
                  </td>
                  <td className="mono">{event.scope || event.event_type}</td>
                  <td>{event.message || event.event_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
};

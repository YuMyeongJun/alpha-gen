import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, PageHeader } from "@/components/common";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IAuditEventRes } from "@/models/interface/res/IDashboardRes";
import { badgeClassBySeverity, formatCompactDateTime } from "@/utils/format";

export interface IAuditPanelProps {
  events: IAuditEventRes[];
}

type AuditFilter = "all" | "info" | "warning" | "critical";

function auditTone(severity?: string): "green" | "amber" | "red" | "gray" {
  const mapped = badgeClassBySeverity(severity);
  if (mapped === "danger") return "red";
  if (mapped === "warning") return "amber";
  return "gray";
}

function severityBucket(severity?: string): Exclude<AuditFilter, "all"> {
  const tone = auditTone(severity);
  if (tone === "red") return "critical";
  if (tone === "amber") return "warning";
  return "info";
}

export const AuditPanel = ({ events }: IAuditPanelProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const [filter, setFilter] = useState<AuditFilter>("all");

  const counts = useMemo(() => {
    const c: Record<AuditFilter, number> = { all: events.length, info: 0, warning: 0, critical: 0 };
    events.forEach((e) => {
      c[severityBucket(e.severity)] += 1;
    });
    return c;
  }, [events]);

  const filtered = useMemo(
    () => (filter === "all" ? events : events.filter((e) => severityBucket(e.severity) === filter)),
    [events, filter],
  );

  const FILTERS: { key: AuditFilter; label: string; tone: "gray" | "amber" | "red" }[] = [
    { key: "all", label: t("panels.audit.filterAll"), tone: "gray" },
    { key: "info", label: t("panels.audit.filterInfo"), tone: "gray" },
    { key: "warning", label: t("panels.audit.filterWarning"), tone: "amber" },
    { key: "critical", label: t("panels.audit.filterCritical"), tone: "red" },
  ];

  return (
    <>
      <PageHeader title={t("panels.audit.title")} subtitle={t("panels.audit.subtitle")} />

      {/* 심각도 필터 */}
      {events.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
          {FILTERS.map(({ key, label, tone }) => (
            <button
              key={key}
              type="button"
              className={`btn btn--sm${filter === key ? " btn--primary" : " btn--ghost"}`}
              onClick={() => setFilter(key)}
            >
              {key !== "all" && <span className={`sev-dot sev-dot--${tone}`} />}
              {label}
              <span className="muted" style={{ fontSize: 10, marginLeft: 4, opacity: 0.75 }}>
                {counts[key]}
              </span>
            </button>
          ))}
        </div>
      )}

      <Card>
        {!filtered.length ? (
          <div className="empty-state">
            {events.length ? t("panels.audit.emptyFiltered") : t("panels.audit.empty")}
          </div>
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
              {filtered.map((event, index) => (
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

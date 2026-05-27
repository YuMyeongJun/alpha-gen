import { useTranslation } from "react-i18next";
import { Badge } from "@/components/common";
import { OpsConsoleNav } from "@/components/pages/OpsConsole/OpsConsoleNav";
import { useDomainLabels } from "@/hooks/useDomainLabels";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";

export interface IOpsConsoleSidebarProps {
  data: IDashboardBundleRes;
}

export const OpsConsoleSidebar = ({ data }: IOpsConsoleSidebarProps) => {
  const { t } = useTranslation();
  const labels = useDomainLabels();
  const workerRunning = Boolean(data.system.worker.running);
  const emergencyActive = Boolean(data.safety.policy.emergency_stop?.enabled);
  const stage = data.safety.policy.stage || data.system.config.operating_stage;

  return (
    <>
      <div className="sidebar__brand">
        <div className="mark">A</div>
        <div className="col">
          <div className="eyebrow">{t("brand.eyebrow")}</div>
          <div className="name">{t("brand.name")}</div>
        </div>
      </div>

      <div className="sidebar__section">
        <div className="sidebar__section-label">{t("nav.sectionCaption")}</div>
        <OpsConsoleNav />
      </div>

      <div className="sidebar__bottom">
        <div className="row" style={{ marginBottom: 10, gap: 8, flexWrap: "wrap" }}>
          <Badge tone="gray" dot>
            {labels.operatingStage(stage)}
          </Badge>
          {workerRunning ? (
            <Badge tone="green" dot>
              {t("domain.worker.running")}
            </Badge>
          ) : (
            <Badge tone="red" solid>
              {t("domain.worker.stopped")}
            </Badge>
          )}
          {emergencyActive ? (
            <Badge tone="red" dot>
              {t("domain.worker.estop")}
            </Badge>
          ) : null}
        </div>
        <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
          v0.4.2-rc · build
          <br />
          <span style={{ color: "var(--ink-2)" }}>{t("sidebar.operator")}</span> · operator@alpha-gen
        </div>
      </div>
    </>
  );
};

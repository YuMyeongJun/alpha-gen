import { useEffect } from "react";
import { Helmet } from "react-helmet-async";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Skeleton from "react-loading-skeleton";
import { Badge } from "@/components/common/Badge";
import { OpsConsoleSidebar } from "@/components/pages/OpsConsole/OpsConsoleSidebar";
import { useDashboardQuery } from "@/hooks/client/dashboard/useDashboardQuery";
import { useSyncStore } from "@/store/syncStore";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { formatDateTime, formatRelative } from "@/utils/format";

export interface IOpsConsoleOutletContext {
  data: IDashboardBundleRes;
}

export const OpsConsoleLayout = () => {
  const { t } = useTranslation();
  const { data, isFetching, isLoading, isError, error, isSuccess } = useDashboardQuery();
  const { label, note, tone, setSyncState } = useSyncStore();

  useEffect(() => {
    if (isLoading) {
      setSyncState(t("ops.syncing"), t("ops.syncingNote"), "warning");
      return;
    }
    if (isError) {
      setSyncState(t("ops.syncError"), error instanceof Error ? error.message : t("ops.unknownError"), "danger");
      return;
    }
    if (isSuccess && data) {
      const workerRunning = Boolean(data.system.worker.running);
      const nextMessage = workerRunning
        ? `${t("ops.autoRefresh")} · ${t("ops.nextRun")} ${formatRelative(data.system.worker.next_cycle_at)}`
        : isFetching
          ? `${t("ops.autoRefresh")} · ${t("ops.syncingNote")}`
          : `${t("ops.autoRefresh")} · ${t("ops.lastSync")} ${formatDateTime(new Date().toISOString())}`;
      setSyncState(t("ops.syncDone"), nextMessage, workerRunning ? "success" : "warning");
    }
  }, [data, error, isError, isFetching, isLoading, isSuccess, setSyncState, t]);

  return (
    <>
      <Helmet>
        <title>{t("app.title")}</title>
      </Helmet>
      <div className="shell">
        <aside className="sidebar">
          {data ? <OpsConsoleSidebar data={data} /> : <Skeleton height={720} />}
        </aside>
        <main className="content">
          <div className="sync-row">
            <Badge tone={tone}>{label}</Badge>
            <span className="sync-note">{note}</span>
          </div>
          {data ? <Outlet context={{ data } satisfies IOpsConsoleOutletContext} /> : <Skeleton height={480} />}
        </main>
      </div>
    </>
  );
};

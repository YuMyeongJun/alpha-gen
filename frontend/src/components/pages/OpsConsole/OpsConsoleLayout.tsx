import { useEffect, useState } from "react";
import { Helmet } from "react-helmet-async";
import { Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import Skeleton from "react-loading-skeleton";
import { Badge, Icon, LanguageToggle, ThemeToggle } from "@/components/common";
import { OpsConsoleSidebar } from "@/components/pages/OpsConsole/OpsConsoleSidebar";
import { useDashboardQuery } from "@/hooks/client/dashboard/useDashboardQuery";
import { useSyncStore } from "@/store/syncStore";
import type { IDashboardBundleRes } from "@/models/interface/res/IDashboardRes";
import { formatDateTime } from "@/utils/format";

export interface IOpsConsoleOutletContext {
  data: IDashboardBundleRes;
}

function syncBadgeTone(tone: string): "green" | "amber" | "red" | "gray" {
  if (tone === "success") return "green";
  if (tone === "danger") return "red";
  if (tone === "warning") return "amber";
  return "gray";
}

export const OpsConsoleLayout = () => {
  const { t } = useTranslation();
  const { data, isFetching, isLoading, isError, error, isSuccess, refetch } = useDashboardQuery();
  const { label, note, tone, setSyncState } = useSyncStore();
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  // 라우트 변경 시 모바일 드로어 닫기
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

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
        ? `${t("ops.autoRefresh")} · ${t("ops.nextRun")} ${formatDateTime(data.system.worker.next_cycle_at)}`
        : isFetching
          ? `${t("ops.autoRefresh")} · ${t("ops.syncingNote")}`
          : `${t("ops.autoRefresh")} · ${t("ops.lastSync")} ${formatDateTime(new Date().toISOString())}`;
      setSyncState(t("ops.syncDone"), nextMessage, workerRunning ? "success" : "warning");
    }
  }, [data, error, isError, isFetching, isLoading, isSuccess, setSyncState, t]);

  return (
    <MotionConfig reducedMotion="user">
      <Helmet>
        <title>{t("app.title")}</title>
      </Helmet>
      <div className="app" data-nav={navOpen ? "open" : "closed"}>
        <aside className="sidebar">
          {data ? <OpsConsoleSidebar data={data} /> : <Skeleton height={720} />}
        </aside>
        {navOpen ? <div className="nav-scrim" onClick={() => setNavOpen(false)} aria-hidden /> : null}
        <main className="main">
          <div className="topbar">
            <div className="row" style={{ gap: 8 }}>
              <button
                type="button"
                className="nav-toggle btn btn--ghost btn--sm"
                aria-label={t("nav.label")}
                aria-expanded={navOpen}
                onClick={() => setNavOpen((v) => !v)}
              >
                <Icon name="menu" size={16} />
              </button>
              <Badge tone={syncBadgeTone(tone)} dot>
                {label}
              </Badge>
              <span className="topbar__sync">{note}</span>
            </div>
            <div className="topbar__right">
              <ThemeToggle />
              <LanguageToggle />
              <span className="kbd">⌘K</span>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => void refetch()}>
                <Icon name="refresh" size={13} />
                {t("ops.refresh")}
              </button>
            </div>
          </div>
          <div className="content">
            <div className="content__inner">
              {data ? (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={location.pathname}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.12, ease: [0.16, 1, 0.3, 1] as const }}
                  >
                    <Outlet context={{ data } satisfies IOpsConsoleOutletContext} />
                  </motion.div>
                </AnimatePresence>
              ) : (
                <Skeleton height={480} />
              )}
            </div>
          </div>
        </main>
      </div>
    </MotionConfig>
  );
};

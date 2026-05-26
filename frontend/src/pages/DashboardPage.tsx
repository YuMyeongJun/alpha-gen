import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { DashboardHero } from "@/components/pages/OpsConsole/panels/DashboardHero";
import { OpsConsoleCharts } from "@/components/pages/OpsConsole/OpsConsoleCharts";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const DashboardPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>{t("pages.dashboard.title")} · {t("app.title")}</title>
      </Helmet>
      <DashboardHero data={data} />
      <section className="grid grid-single">
        <article className="panel panel-wide">
          <div className="panel-header">
            <h3>{t("pages.dashboard.charts")}</h3>
          </div>
          <OpsConsoleCharts portfolio={data.portfolio} signals={data.signals} />
        </article>
      </section>
    </>
  );
};

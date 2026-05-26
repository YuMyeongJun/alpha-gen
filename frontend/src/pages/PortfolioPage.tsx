import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { PortfolioPanel } from "@/components/pages/OpsConsole/panels/PortfolioPanel";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const PortfolioPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>{t("pages.portfolio.title")} · {t("app.title")}</title>
      </Helmet>
      <section className="grid grid-single">
        <PortfolioPanel portfolio={data.portfolio} signals={data.signals} />
      </section>
    </>
  );
};

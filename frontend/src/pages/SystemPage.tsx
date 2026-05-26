import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { SystemPanel } from "@/components/pages/OpsConsole/panels/SystemPanel";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const SystemPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>{t("pages.system.title")} · {t("app.title")}</title>
      </Helmet>
      <section className="grid grid-single">
        <SystemPanel system={data.system} policy={data.safety.policy} />
      </section>
    </>
  );
};

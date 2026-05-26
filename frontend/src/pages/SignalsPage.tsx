import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { SignalsPanel } from "@/components/pages/OpsConsole/panels/SignalsPanel";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const SignalsPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>{t("pages.signals.title")} · {t("app.title")}</title>
      </Helmet>
      <section className="grid grid-single">
        <SignalsPanel signals={data.signals.signals || []} />
      </section>
    </>
  );
};

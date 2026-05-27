import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { AuditPanel } from "@/components/pages/OpsConsole/panels/AuditPanel";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const AuditPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>
          {t("pages.audit.title")} · {t("app.title")}
        </title>
      </Helmet>
      <AuditPanel events={data.audit.events || []} />
    </>
  );
};

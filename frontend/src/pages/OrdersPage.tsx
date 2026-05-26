import { Helmet } from "react-helmet-async";
import { useTranslation } from "react-i18next";
import { OrdersPanel } from "@/components/pages/OpsConsole/panels/OrdersPanel";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const OrdersPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();

  return (
    <>
      <Helmet>
        <title>{t("pages.orders.title")} · {t("app.title")}</title>
      </Helmet>
      <section className="grid grid-single">
        <OrdersPanel orders={data.orders.orders || []} />
      </section>
    </>
  );
};

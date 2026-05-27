import { Helmet } from "react-helmet-async";
import { toast } from "react-toastify";
import { useTranslation } from "react-i18next";
import { BacktestsPanel } from "@/components/pages/OpsConsole/panels/BacktestsPanel";
import { useOpsMutations } from "@/hooks/client/safety/useSafetyMutations";
import { useOpsConsoleContext } from "@/hooks/useOpsConsoleContext";

export const BacktestsPage = () => {
  const { t } = useTranslation();
  const { data } = useOpsConsoleContext();
  const { runBacktest } = useOpsMutations();

  const handleRunBacktest = async () => {
    try {
      await runBacktest.mutateAsync({ days: 30, initial_cash: 10000000 });
      toast.success(t("pages.backtests.runDone"));
    } catch (backtestError) {
      toast.error(backtestError instanceof Error ? backtestError.message : t("pages.backtests.runFailed"));
    }
  };

  return (
    <>
      <Helmet>
        <title>
          {t("pages.backtests.title")} · {t("app.title")}
        </title>
      </Helmet>
      <BacktestsPanel runs={data.backtests.runs || []} onRunBacktest={() => void handleRunBacktest()} />
    </>
  );
};

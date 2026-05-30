import { Helmet } from "react-helmet-async";
import { StocksPanel } from "@/components/pages/OpsConsole/panels/StocksPanel";

export const StocksPage = () => (
  <>
    <Helmet>
      <title>종목 관리 · Alpha-Gen</title>
    </Helmet>
    <StocksPanel />
  </>
);

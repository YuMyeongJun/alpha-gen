import { Navigate, Route, Routes } from "react-router-dom";
import { OpsConsoleLayout } from "@/components/pages/OpsConsole/OpsConsoleLayout";
import { AuditPage } from "@/pages/AuditPage";
import { BacktestsPage } from "@/pages/BacktestsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { OrdersPage } from "@/pages/OrdersPage";
import { PortfolioPage } from "@/pages/PortfolioPage";
import { SignalsPage } from "@/pages/SignalsPage";
import { StocksPage } from "@/pages/StocksPage";
import { SystemPage } from "@/pages/SystemPage";

export const AppRouter = () => (
  <Routes>
    <Route path="/" element={<OpsConsoleLayout />}>
      <Route index element={<DashboardPage />} />
      <Route path="dashboard" element={<Navigate to="/" replace />} />
      <Route path="portfolio" element={<PortfolioPage />} />
      <Route path="signals" element={<SignalsPage />} />
      <Route path="orders" element={<OrdersPage />} />
      <Route path="backtests" element={<BacktestsPage />} />
      <Route path="audit" element={<AuditPage />} />
      <Route path="stocks" element={<StocksPage />} />
      <Route path="system" element={<SystemPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);

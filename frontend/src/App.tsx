import { HelmetProvider } from "react-helmet-async";
import { BrowserRouter } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import { QueryProvider } from "@/hooks/providers/QueryProvider";
import { AppRouter } from "@/routers";
import "@/translations/i18n";
import "@/styles.scss";
import "react-toastify/dist/ReactToastify.css";
import "react-loading-skeleton/dist/skeleton.css";

export const App = () => (
  <HelmetProvider>
    <QueryProvider>
      <BrowserRouter>
        <AppRouter />
        <ToastContainer position="bottom-right" autoClose={3000} theme="colored" />
      </BrowserRouter>
    </QueryProvider>
  </HelmetProvider>
);

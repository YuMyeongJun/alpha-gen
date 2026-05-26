import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

const NAV_ITEMS = [
  { to: "/", end: true, labelKey: "nav.dashboard" },
  { to: "/portfolio", end: false, labelKey: "nav.portfolio" },
  { to: "/signals", end: false, labelKey: "nav.signals" },
  { to: "/orders", end: false, labelKey: "nav.orders" },
  { to: "/backtests", end: false, labelKey: "nav.backtests" },
  { to: "/audit", end: false, labelKey: "nav.audit" },
  { to: "/system", end: false, labelKey: "nav.system" },
] as const;

export const OpsConsoleNav = () => {
  const { t } = useTranslation();

  return (
    <nav className="sidebar-nav" aria-label={t("nav.label")}>
      <ul className="sidebar-nav-list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? "sidebar-nav-link active" : "sidebar-nav-link")}>
              {t(item.labelKey)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
};

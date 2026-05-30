import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Icon, type IconName } from "@/components/common";

const NAV_ITEMS: Array<{ to: string; end: boolean; labelKey: string; icon: IconName }> = [
  { to: "/", end: true, labelKey: "nav.dashboard", icon: "dashboard" },
  { to: "/portfolio", end: false, labelKey: "nav.portfolio", icon: "portfolio" },
  { to: "/signals", end: false, labelKey: "nav.signals", icon: "signal" },
  { to: "/orders", end: false, labelKey: "nav.orders", icon: "orders" },
  { to: "/backtests", end: false, labelKey: "nav.backtests", icon: "backtest" },
  { to: "/audit", end: false, labelKey: "nav.audit", icon: "audit" },
  { to: "/stocks", end: false, labelKey: "nav.stocks", icon: "stocks" },
  { to: "/system", end: false, labelKey: "nav.system", icon: "system" },
];

export const OpsConsoleNav = () => {
  const { t } = useTranslation();

  return (
    <nav className="nav" aria-label={t("nav.label")}>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `nav__item${isActive ? " active" : ""}`}
        >
          <Icon name={item.icon} size={15} />
          <span>{t(item.labelKey)}</span>
        </NavLink>
      ))}
    </nav>
  );
};

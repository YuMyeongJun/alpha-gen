import type { ReactNode } from "react";

export type IconName =
  | "dashboard"
  | "portfolio"
  | "signal"
  | "orders"
  | "backtest"
  | "audit"
  | "system"
  | "stocks"
  | "play"
  | "pause"
  | "refresh"
  | "bolt"
  | "stop"
  | "warn";

export interface IIconProps {
  name: IconName;
  size?: number;
  className?: string;
}

const PATHS: Record<IconName, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  portfolio: <path d="M3 7h18M3 12h18M3 17h12" />,
  signal: <path d="M3 17l5-7 4 4 5-9 4 6" />,
  orders: (
    <>
      <path d="M5 4h14l-1.4 12.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8L5 4z" />
      <path d="M9 8h6" />
    </>
  ),
  backtest: (
    <>
      <path d="M4 4v16h16" />
      <path d="M8 14l3-4 3 2 4-6" />
    </>
  ),
  audit: (
    <>
      <path d="M4 4h12l4 4v12H4z" />
      <path d="M8 12h8M8 16h8M8 8h4" />
    </>
  ),
  system: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
  stocks: (
    <>
      <rect x="3" y="14" width="4" height="7" rx="1" />
      <rect x="10" y="9" width="4" height="12" rx="1" />
      <rect x="17" y="3" width="4" height="18" rx="1" />
    </>
  ),
  play: <path d="M6 4l14 8L6 20z" fill="currentColor" stroke="none" />,
  pause: (
    <>
      <rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none" />
      <rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none" />
    </>
  ),
  refresh: (
    <>
      <path d="M4 12a8 8 0 0 1 14-5.3M20 4v4h-4" />
      <path d="M20 12a8 8 0 0 1-14 5.3M4 20v-4h4" />
    </>
  ),
  bolt: <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor" stroke="none" />,
  stop: <rect x="5" y="5" width="14" height="14" rx="2" />,
  warn: (
    <>
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v5M12 18.5v.01" />
    </>
  ),
};

export const Icon = ({ name, size = 16, className = "" }: IIconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.6}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`nav__icon ${className}`.trim()}
    aria-hidden
  >
    {PATHS[name]}
  </svg>
);

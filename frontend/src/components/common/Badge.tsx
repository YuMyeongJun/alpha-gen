import type { CSSProperties, ReactNode } from "react";
import classNames from "classnames";

export type BadgeTone = "green" | "red" | "blue" | "gray" | "amber" | "success" | "warning" | "danger" | "live";

const TONE_ALIAS: Record<string, BadgeTone> = {
  success: "green",
  warning: "amber",
  danger: "red",
  live: "blue",
};

export interface IBadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  solid?: boolean;
  className?: string;
  style?: CSSProperties;
}

export const Badge = ({ children, tone = "gray", dot = false, solid = false, className, style }: IBadgeProps) => {
  const resolved = TONE_ALIAS[tone] || tone;
  const cls = solid && resolved === "red"
    ? "badge badge--solid-red"
    : classNames(`badge badge--${resolved}`, { "badge--dot": dot }, className);

  return <span className={cls} style={style}>{children}</span>;
};

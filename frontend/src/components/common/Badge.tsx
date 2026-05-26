import type { ReactNode } from "react";
import classNames from "classnames";

export interface IBadgeProps {
  children: ReactNode;
  tone?: "success" | "warning" | "danger" | "live";
  className?: string;
}

export const Badge = ({ children, tone, className }: IBadgeProps) => (
  <span className={classNames("badge", tone, className)}>{children}</span>
);

import type { ReactNode } from "react";
import classNames from "classnames";

export interface IMetricProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  sub?: ReactNode;
  tone?: "danger";
  /** "hero" = 화면당 1개, 헤드라인 숫자용 (--fs-hero). 기본값은 기존 크기 그대로. */
  size?: "hero";
  right?: ReactNode;
  className?: string;
}

export const Metric = ({ label, value, unit, sub, tone, size, right, className }: IMetricProps) => (
  <div
    className={classNames(
      "metric",
      tone === "danger" && "metric--danger",
      size === "hero" && "metric--hero",
      className,
    )}
  >
    <div className="metric__label">{label}</div>
    <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between" }}>
      <div className="metric__value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </div>
      {right}
    </div>
    {sub ? <div className="metric__sub">{sub}</div> : null}
  </div>
);

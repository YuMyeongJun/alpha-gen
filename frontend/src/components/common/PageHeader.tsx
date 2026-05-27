import type { ReactNode } from "react";

export interface IPageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  eyebrow?: ReactNode;
}

export const PageHeader = ({ title, subtitle, right, eyebrow }: IPageHeaderProps) => (
  <header style={{ marginBottom: 18 }}>
    {(eyebrow || right) && (
      <div className="row" style={{ justifyContent: "space-between", marginBottom: eyebrow ? 8 : 0 }}>
        {eyebrow ? <span className="badge badge--gray">{eyebrow}</span> : <span />}
        {right}
      </div>
    )}
    <h1 className="h-title">{title}</h1>
    {subtitle ? <p className="h-sub">{subtitle}</p> : null}
  </header>
);

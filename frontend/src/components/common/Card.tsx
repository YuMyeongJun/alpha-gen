import type { CSSProperties, ReactNode } from "react";
import classNames from "classnames";

export interface ICardProps {
  title?: ReactNode;
  eyebrow?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export const Card = ({ title, eyebrow, right, children, className, style }: ICardProps) => (
  <section className={classNames("card", className)} style={style}>
    {(title || right) && (
      <header className="card__head">
        <div>
          {eyebrow ? <div className="card__eyebrow">{eyebrow}</div> : null}
          {title ? <div className="card__title">{title}</div> : null}
        </div>
        {right}
      </header>
    )}
    {children}
  </section>
);

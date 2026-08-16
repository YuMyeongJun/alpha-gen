import type { ReactNode } from "react";
import { motion } from "framer-motion";
import classNames from "classnames";

export interface IMetricGridProps {
  children: ReactNode;
  columns?: 2 | 4;
  className?: string;
}

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
} as const;

const itemVariants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.16, ease: [0.16, 1, 0.3, 1] as const } },
} as const;

/** grid-4/grid-2 요약 카드 컨테이너 — 마운트 시 살짝 스태거 페이드인. prefers-reduced-motion은 MotionConfig(전역)가 처리. */
export const MetricGrid = ({ children, columns = 4, className }: IMetricGridProps) => (
  <motion.div
    className={classNames("metric-grid", columns === 4 ? "grid-4" : "grid-2", className)}
    variants={containerVariants}
    initial="hidden"
    animate="show"
  >
    {Array.isArray(children)
      ? children.filter(Boolean).map((child, i) => (
          <motion.div key={i} variants={itemVariants} style={{ minWidth: 0 }}>
            {child}
          </motion.div>
        ))
      : children}
  </motion.div>
);

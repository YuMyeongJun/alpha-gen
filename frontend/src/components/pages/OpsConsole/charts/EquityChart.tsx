import { useTranslation } from "react-i18next";

export interface IEquityPoint {
  t: string;
  v: number;
}

export interface IEquityChartProps {
  data: IEquityPoint[];
  baseline: number;
  width?: number;
  height?: number;
}

function formatKrw(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}억`;
  if (v >= 1e4) return `${Math.round(v / 1e4).toLocaleString()}만`;
  return Math.round(v).toLocaleString();
}

export const EquityChart = ({ data, baseline, width = 720, height = 220 }: IEquityChartProps) => {
  const { t } = useTranslation();
  if (!data.length) {
    return <div className="empty-state">{t("chart.empty")}</div>;
  }

  const padL = 56;
  const padR = 12;
  const padT = 14;
  const padB = 28;
  const W = width;
  const H = height;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const values = data.map((d) => d.v);
  const minV = Math.min(baseline, ...values);
  const maxV = Math.max(baseline, ...values);
  const span = Math.max(1, maxV - minV);
  const yMin = minV - span * 0.06;
  const yMax = maxV + span * 0.06;

  const x = (i: number) => padL + (i / Math.max(1, data.length - 1)) * innerW;
  const y = (v: number) => padT + (1 - (v - yMin) / (yMax - yMin)) * innerH;

  const bands: Array<[number, number]> = [];
  let runStart: number | null = null;
  data.forEach((d, i) => {
    if (d.v < baseline) {
      if (runStart === null) runStart = i;
    } else if (runStart !== null) {
      bands.push([runStart, i - 1]);
      runStart = null;
    }
  });
  if (runStart !== null) bands.push([runStart, data.length - 1]);

  const pts = data.map((d, i) => `${x(i)},${y(d.v)}`);
  const linePath = `M ${pts.join(" L ")}`;
  const areaPath = `${linePath} L ${x(data.length - 1)},${y(yMin)} L ${x(0)},${y(yMin)} Z`;

  const ticks = 4;
  const tickValues = Array.from({ length: ticks + 1 }, (_, k) => yMin + (k / ticks) * (yMax - yMin));

  const xTickIdx =
    data.length <= 4
      ? data.map((_, i) => i)
      : [0, Math.floor(data.length * 0.33), Math.floor(data.length * 0.66), data.length - 1];

  const lastV = data[data.length - 1].v;
  const lastY = y(lastV);
  const lastX = x(data.length - 1);

  return (
    <div className="chart-wrap">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--ink-1)" stopOpacity="0.1" />
            <stop offset="100%" stopColor="var(--ink-1)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="dd-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--red-500)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--red-500)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {bands.map(([a, b], i) => (
          <rect
            key={i}
            x={x(a)}
            y={padT}
            width={Math.max(2, x(b) - x(a))}
            height={innerH}
            fill="url(#dd-fill)"
          />
        ))}

        {tickValues.map((v, i) => {
          const yy = y(v);
          return (
            <g key={i}>
              <line x1={padL} x2={W - padR} y1={yy} y2={yy} stroke="var(--border)" strokeWidth="1" />
              <text
                x={padL - 6}
                y={yy + 3.5}
                textAnchor="end"
                fontSize="10"
                fill="var(--ink-3)"
                fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
              >
                {formatKrw(v)}
              </text>
            </g>
          );
        })}

        <line
          x1={padL}
          x2={W - padR}
          y1={y(baseline)}
          y2={y(baseline)}
          stroke="var(--ink-3)"
          strokeDasharray="4 4"
          strokeWidth="1"
        />
        <text x={W - padR} y={y(baseline) - 6} textAnchor="end" fontSize="10.5" fill="var(--ink-3)">
          {t("chart.baseline")} {formatKrw(baseline)}
        </text>

        <path d={areaPath} fill="url(#eq-fill)" />
        <path d={linePath} stroke="var(--ink-1)" strokeWidth="1.5" fill="none" />

        <circle cx={lastX} cy={lastY} r="3.5" fill="var(--bg)" stroke="var(--ink-1)" strokeWidth="1.5" />
        <g>
          <rect x={lastX - 56} y={lastY - 28} width="56" height="20" rx="4" fill="var(--ink-1)" />
          <text
            x={lastX - 28}
            y={lastY - 14}
            textAnchor="middle"
            fontSize="11"
            fill="var(--bg)"
            fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
          >
            {formatKrw(lastV)}
          </text>
        </g>

        {xTickIdx.map((i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize="10.5" fill="var(--ink-3)">
            {data[i].t}
          </text>
        ))}
      </svg>

      <div className="chart-legend" style={{ marginTop: 4 }}>
        <span>
          <span className="swatch" style={{ background: "var(--ink-1)" }} />
          {t("chart.totalAsset")}
        </span>
        <span>
          <span className="swatch dashed" />
          {t("chart.baseline")}
        </span>
        <span>
          <span className="swatch" style={{ background: "rgba(226,75,74,0.32)" }} />
          {t("chart.drawdown")}
        </span>
      </div>
    </div>
  );
};

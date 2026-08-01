/* global React */
const { useState, useEffect, useRef, useMemo } = React;

/* ============================================================
   Icons — minimal stroke set
   ============================================================ */
const Icon = ({ name, size = 16, className = "" }) => {
  const common = {
    width: size, height: size, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor", strokeWidth: 1.6,
    strokeLinecap: "round", strokeLinejoin: "round",
    className: "nav__icon " + className,
  };
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></>,
    portfolio: <><path d="M3 7h18M3 12h18M3 17h12"/></>,
    signal: <><path d="M3 17l5-7 4 4 5-9 4 6"/></>,
    orders: <><path d="M5 4h14l-1.4 12.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8L5 4z"/><path d="M9 8h6"/></>,
    backtest: <><path d="M4 4v16h16"/><path d="M8 14l3-4 3 2 4-6"/></>,
    audit: <><path d="M4 4h12l4 4v12H4z"/><path d="M8 12h8M8 16h8M8 8h4"/></>,
    system: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></>,
    play: <><path d="M6 4l14 8L6 20z" fill="currentColor" stroke="none"/></>,
    pause: <><rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none"/><rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none"/></>,
    refresh: <><path d="M4 12a8 8 0 0 1 14-5.3M20 4v4h-4"/><path d="M20 12a8 8 0 0 1-14 5.3M4 20v-4h4"/></>,
    bolt: <><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor" stroke="none"/></>,
    stop: <><rect x="5" y="5" width="14" height="14" rx="2"/></>,
    chevron: <><path d="M8 5l8 7-8 7"/></>,
    chevronDown: <><path d="M5 8l7 8 7-8"/></>,
    check: <><path d="M4 12l5 5 11-12"/></>,
    warn: <><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18.5v.01"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 8v.01M11 12h1v5h1"/></>,
    close: <><path d="M5 5l14 14M19 5L5 19"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrowUp: <><path d="M12 19V5M5 12l7-7 7 7"/></>,
    arrowDown: <><path d="M12 5v14M19 12l-7 7-7-7"/></>,
  };
  return (
    <svg {...common}>{paths[name] || null}</svg>
  );
};

/* ============================================================
   Badges, Pills, Sync indicator
   ============================================================ */
const Badge = ({ tone = "gray", dot = false, solid = false, children }) => {
  const cls = solid && tone === "red"
    ? "badge badge--solid-red"
    : `badge badge--${tone}${dot ? " badge--dot" : ""}`;
  return <span className={cls}>{children}</span>;
};

const StagePills = ({ value, onChange }) => {
  const stages = [
    { id: "shadow", label: "Shadow", desc: "주문 비활성" },
    { id: "paper",  label: "Paper",  desc: "모의 거래" },
    { id: "live",   label: "Live",   desc: "실거래" },
  ];
  return (
    <div className="stage-pills" role="tablist">
      {stages.map(s => (
        <button
          key={s.id}
          role="tab"
          data-stage={s.id}
          className={"stage-pill" + (value === s.id ? " active" : "")}
          onClick={() => onChange && onChange(s.id)}
        >
          <span className="dot"/>
          {s.label}
        </button>
      ))}
    </div>
  );
};

/* ============================================================
   Metric card
   ============================================================ */
const Metric = ({ label, value, unit, sub, tone, right }) => (
  <div className={"metric" + (tone === "danger" ? " metric--danger" : "")}>
    <div className="metric__label">{label}</div>
    <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between" }}>
      <div className="metric__value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {right}
    </div>
    {sub && <div className="metric__sub">{sub}</div>}
  </div>
);

/* ============================================================
   Card + section header
   ============================================================ */
const Card = ({ title, eyebrow, right, children, style, className = "" }) => (
  <section className={"card " + className} style={style}>
    {(title || right) && (
      <header className="card__head">
        <div>
          {eyebrow && <div className="card__eyebrow">{eyebrow}</div>}
          {title && <div className="card__title">{title}</div>}
        </div>
        {right}
      </header>
    )}
    {children}
  </section>
);

/* ============================================================
   Equity Chart — area + baseline + drawdown shading
   ============================================================ */
const EquityChart = ({ data, baseline, width = 720, height = 220 }) => {
  // data: [{ t: "09:00", v: 10_000_000 }, ...]
  const padL = 48, padR = 16, padT = 14, padB = 28;
  const W = width, H = height;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const values = data.map(d => d.v);
  const minV = Math.min(baseline, ...values);
  const maxV = Math.max(baseline, ...values);
  const span = Math.max(1, maxV - minV);
  // pad y range by 6%
  const yMin = minV - span * 0.06;
  const yMax = maxV + span * 0.06;

  const x = i => padL + (i / Math.max(1, data.length - 1)) * innerW;
  const y = v => padT + (1 - (v - yMin) / (yMax - yMin)) * innerH;

  // Drawdown bands: contiguous runs below baseline
  const bands = [];
  let runStart = null;
  data.forEach((d, i) => {
    if (d.v < baseline) {
      if (runStart === null) runStart = i;
    } else {
      if (runStart !== null) { bands.push([runStart, i - 1]); runStart = null; }
    }
  });
  if (runStart !== null) bands.push([runStart, data.length - 1]);

  // Line + area paths
  const pts = data.map((d, i) => `${x(i)},${y(d.v)}`);
  const linePath = "M " + pts.join(" L ");
  const areaPath = linePath
    + ` L ${x(data.length - 1)},${y(yMin)} L ${x(0)},${y(yMin)} Z`;

  // Y ticks
  const ticks = 4;
  const tickValues = Array.from({ length: ticks + 1 }, (_, k) =>
    yMin + (k / ticks) * (yMax - yMin)
  );

  // X ticks — first, middle, last
  const xTickIdx = data.length <= 4
    ? data.map((_, i) => i)
    : [0, Math.floor(data.length * 0.33), Math.floor(data.length * 0.66), data.length - 1];

  const fmtKRW = v => {
    if (v >= 1e8) return (v / 1e8).toFixed(2) + "억";
    if (v >= 1e4) return Math.round(v / 1e4).toLocaleString() + "만";
    return Math.round(v).toLocaleString();
  };

  const lastV = data[data.length - 1].v;
  const lastY = y(lastV);
  const lastX = x(data.length - 1);

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }}>
        <defs>
          <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"  stopColor="#0f1116" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#0f1116" stopOpacity="0.00" />
          </linearGradient>
          <linearGradient id="dd-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"  stopColor="#E24B4A" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#E24B4A" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Drawdown bands */}
        {bands.map(([a, b], i) => {
          const xa = x(a), xb = x(b);
          return (
            <rect key={i} x={xa} y={padT} width={Math.max(2, xb - xa)} height={innerH}
              fill="url(#dd-fill)" />
          );
        })}

        {/* Y grid + labels */}
        {tickValues.map((v, i) => {
          const yy = y(v);
          return (
            <g key={i}>
              <line x1={padL} x2={W - padR} y1={yy} y2={yy}
                stroke="rgba(15,17,22,0.06)" strokeWidth="1" />
              <text x={padL - 8} y={yy + 3.5} textAnchor="end"
                fontSize="10.5" fill="#6b6f78"
                fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
                {fmtKRW(v)}
              </text>
            </g>
          );
        })}

        {/* Baseline (dashed) */}
        <line x1={padL} x2={W - padR} y1={y(baseline)} y2={y(baseline)}
          stroke="#6b6f78" strokeDasharray="4 4" strokeWidth="1" />
        <text x={W - padR} y={y(baseline) - 6} textAnchor="end"
          fontSize="10.5" fill="#6b6f78">
          기준선 {fmtKRW(baseline)}
        </text>

        {/* Area + line */}
        <path d={areaPath} fill="url(#eq-fill)" />
        <path d={linePath} stroke="#0f1116" strokeWidth="1.5" fill="none" />

        {/* Last point */}
        <circle cx={lastX} cy={lastY} r="3.5" fill="#fff" stroke="#0f1116" strokeWidth="1.5"/>
        <g>
          <rect x={lastX - 56} y={lastY - 28} width="56" height="20" rx="4"
            fill="#0f1116" />
          <text x={lastX - 28} y={lastY - 14} textAnchor="middle" fontSize="11" fill="#fff"
            fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
            {fmtKRW(lastV)}
          </text>
        </g>

        {/* X labels */}
        {xTickIdx.map(i => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle"
            fontSize="10.5" fill="#6b6f78">
            {data[i].t}
          </text>
        ))}
      </svg>

      <div className="chart-legend" style={{ marginTop: 4 }}>
        <span><span className="swatch" style={{ background: "#0f1116" }}/>총자산</span>
        <span><span className="swatch dashed"/>기준선 (초기 원금)</span>
        <span><span className="swatch" style={{ background: "rgba(226,75,74,0.32)" }}/>드로우다운 구간</span>
      </div>
    </div>
  );
};

/* ============================================================
   Horizontal bar chart for signal distribution
   ============================================================ */
const SignalBars = ({ rows }) => {
  // rows: [{ key, label, value, tone }]
  const max = Math.max(1, ...rows.map(r => r.value));
  const toneColor = {
    green: "#639922", red: "#E24B4A", blue: "#378ADD", gray: "#9b9ea6"
  };
  return (
    <div>
      {rows.map(r => (
        <div key={r.key} className="hbar-row">
          <div className="hbar-row__label">
            <span className="dot" style={{ background: toneColor[r.tone] }}/>
            {r.label}
          </div>
          <div className="hbar-row__track">
            <div className="hbar-row__fill"
              style={{ width: ((r.value / max) * 100) + "%", background: toneColor[r.tone] }}/>
          </div>
          <div className="hbar-row__val">{r.value}건</div>
        </div>
      ))}
    </div>
  );
};

/* ============================================================
   Toast hook
   ============================================================ */
const useToasts = () => {
  const [toasts, setToasts] = useState([]);
  const push = (msg) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, msg }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 2600);
  };
  const view = (
    <div className="toast-wrap">
      {toasts.map(t => (
        <div key={t.id} className="toast">
          <Icon name="check" size={14} />
          <span>{t.msg}</span>
        </div>
      ))}
    </div>
  );
  return [push, view];
};

/* ============================================================
   Confirm dialog
   ============================================================ */
const ConfirmDialog = ({ open, title, body, danger, confirmText, cancelText, onCancel, onConfirm }) => {
  if (!open) return null;
  return (
    <div className="scrim" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
          <button className="btn" onClick={onCancel}>{cancelText || "취소"}</button>
          <button className={"btn " + (danger ? "btn--danger" : "btn--primary")} onClick={onConfirm}>
            {confirmText || "확인"}
          </button>
        </div>
      </div>
    </div>
  );
};

/* Export to window */
Object.assign(window, {
  Icon, Badge, StagePills, Metric, Card,
  EquityChart, SignalBars,
  useToasts, ConfirmDialog,
});

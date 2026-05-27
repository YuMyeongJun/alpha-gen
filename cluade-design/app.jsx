/* global React, ReactDOM */
/* depends on components.jsx and pages.jsx (window globals) */
const { useState: useState_a, useEffect: useEffect_a } = React;

const NAV = [
  { id: "dashboard", label: "대시보드", icon: "dashboard" },
  { id: "portfolio", label: "포트폴리오", icon: "portfolio" },
  { id: "signals",   label: "시그널",   icon: "signal" },
  { id: "orders",    label: "주문",     icon: "orders" },
  { id: "backtest",  label: "백테스트", icon: "backtest" },
  { id: "audit",     label: "감사",     icon: "audit" },
  { id: "system",    label: "시스템",   icon: "system" },
];

const PAGE_LABEL = {
  "01": "Dashboard", "02": "Portfolio", "03": "Signals", "04": "Orders",
  "05": "Backtest", "06": "Audit", "07": "System"
};

const Sidebar = ({ active, onNav, ctx }) => {
  return (
    <aside className="sidebar" data-screen-label="Sidebar">
      <div className="sidebar__brand">
        <div className="mark">A</div>
        <div className="col">
          <div className="eyebrow">ALPHA-GEN</div>
          <div className="name">Trading Console</div>
        </div>
      </div>

      <div className="sidebar__section">
        <div className="sidebar__section-label">탐색</div>
        <nav className="nav">
          {NAV.map(n => (
            <button key={n.id}
              className={"nav__item" + (active === n.id ? " active" : "")}
              onClick={() => onNav(n.id)}>
              <Icon name={n.icon} size={15} />
              <span>{n.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="sidebar__bottom">
        <div className="row" style={{ marginBottom: 10, gap: 8 }}>
          <Badge tone="gray" dot>{ctx.stage}</Badge>
          {ctx.worker === "STOPPED"
            ? <Badge tone="red" solid>STOPPED</Badge>
            : ctx.worker === "RUNNING"
            ? <Badge tone="green" dot>RUNNING</Badge>
            : <Badge tone="gray" dot>IDLE</Badge>}
        </div>
        <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
          v0.4.2-rc · build #841<br/>
          <span style={{ color: "var(--ink-2)" }}>운영자</span> · operator@alpha-gen
        </div>
      </div>
    </aside>
  );
};

const Topbar = ({ active, ctx }) => {
  const now = new Date();
  const fmt = `${String(now.getMonth()+1).padStart(2,"0")}. ${String(now.getDate()).padStart(2,"0")}. ${now.getHours() < 12 ? "오전" : "오후"} ${String(((now.getHours()+11)%12)+1).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}:${String(now.getSeconds()).padStart(2,"0")}`;

  return (
    <div className="topbar">
      <div className="row" style={{ gap: 8 }}>
        <Badge tone="green" dot>동기화 완료</Badge>
        <span className="topbar__sync">
          자동 갱신 · 마지막 동기화 <strong>{fmt}</strong>
        </span>
      </div>
      <div className="topbar__right">
        <div className="row" style={{ gap: 8 }}>
          <span className="kbd">⌘K</span>
          <button className="btn btn--ghost btn--sm">
            <Icon name="refresh" size={13}/>
            새로고침
          </button>
        </div>
      </div>
    </div>
  );
};

/* ============================================================
   App
   ============================================================ */
const App = () => {
  const [active, setActive] = useState_a("dashboard");
  const [stage, setStage]   = useState_a("shadow");
  const [worker, setWorker] = useState_a("STOPPED");
  const [push, toastView]   = useToasts();

  const ctx = {
    stage, setStage,
    worker, setWorker,
    toast: push,
    totalAssets: 10_000_000,
    cash: 10_000_000,
    pnlPct: 0.00,
  };

  const Page = ({
    dashboard: DashboardPage,
    portfolio: PortfolioPage,
    signals:   SignalsPage,
    orders:    OrdersPage,
    backtest:  BacktestsPage,
    audit:     AuditPage,
    system:    SystemPage,
  })[active];

  const screenLabel = ({
    dashboard: "01 Dashboard",
    portfolio: "02 Portfolio",
    signals:   "03 Signals",
    orders:    "04 Orders",
    backtest:  "05 Backtest",
    audit:     "06 Audit",
    system:    "07 System",
  })[active];

  return (
    <div className="app">
      <Sidebar active={active} onNav={setActive} ctx={ctx} />
      <main className="main" data-screen-label={screenLabel}>
        <Topbar active={active} ctx={ctx} />
        <div className="content">
          <div className="content__inner">
            <Page ctx={ctx} />
          </div>
        </div>
      </main>
      {toastView}
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

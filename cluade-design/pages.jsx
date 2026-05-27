/* global React */
/* depends on components.jsx (window globals) */
const { useState: useState_d, useEffect: useEffect_d, useMemo: useMemo_d } = React;

/* ============================================================
   Mock data
   ============================================================ */
const generateEquity = () => {
  const base = 10_000_000;
  const points = 32;
  let v = base;
  const out = [];
  for (let i = 0; i < points; i++) {
    // Synthetic: small drift + a drawdown around 8-14, then recovery
    const drift = i < 8 ? 0.0005 : i < 14 ? -0.0035 : i < 22 ? 0.0010 : 0.0008;
    const noise = (Math.sin(i * 1.3) + Math.cos(i * 0.7)) * 0.0008;
    v = v * (1 + drift + noise);
    const hh = String(9 + Math.floor(i / 4)).padStart(2, "0");
    const mm = String((i % 4) * 15).padStart(2, "0");
    out.push({ t: `${hh}:${mm}`, v: Math.round(v) });
  }
  return { data: out, baseline: base };
};

const EQUITY = generateEquity();

const SIGNAL_ROWS = [
  { key: "watch", label: "WATCH",   value: 16, tone: "gray" },
  { key: "buy",   label: "BUY 후보", value: 4,  tone: "green" },
  { key: "sell",  label: "SELL 후보", value: 2,  tone: "red" },
  { key: "skip",  label: "SKIP",    value: 1,  tone: "gray" },
];

const BACKTESTS = [
  { id: 4, when: "05. 27. 오후 03:18", ret: 0.84,  win: 100.0, trades: 4, pnl: 84210 },
  { id: 3, when: "05. 27. 오전 12:58", ret: 0.54,  win: 100.0, trades: 3, pnl: 53650 },
  { id: 2, when: "05. 27. 오전 12:06", ret: 0.10,  win: 100.0, trades: 1, pnl: 9864 },
  { id: 1, when: "05. 27. 오전 12:06", ret: 0.32,  win: 100.0, trades: 1, pnl: 31579 },
  { id: 0, when: "05. 26. 오후 09:42", ret: -0.22, win: 33.3,  trades: 3, pnl: -22480 },
];

const SIGNALS_LIST = [
  { ticker: "005930", name: "삼성전자",   side: "WATCH", score: 0.42, price: "74,800", chg: -0.27 },
  { ticker: "000660", name: "SK하이닉스", side: "BUY",   score: 0.81, price: "208,500", chg: +1.84 },
  { ticker: "035420", name: "NAVER",     side: "WATCH", score: 0.52, price: "182,400", chg: +0.55 },
  { ticker: "207940", name: "삼성바이오로직스", side: "SELL", score: 0.27, price: "812,000", chg: -1.20 },
  { ticker: "035720", name: "카카오",     side: "WATCH", score: 0.49, price: "41,150",  chg: -0.36 },
  { ticker: "068270", name: "셀트리온",   side: "BUY",   score: 0.74, price: "178,300", chg: +0.79 },
  { ticker: "005380", name: "현대차",     side: "WATCH", score: 0.55, price: "236,500", chg: +0.21 },
  { ticker: "051910", name: "LG화학",     side: "SELL",  score: 0.30, price: "348,000", chg: -2.41 },
];

const ORDERS = [
  { id: "ORD-2841", t: "10:02:41", sym: "000660", side: "BUY",  qty: 2, status: "FILLED",   px: "208,500", note: "paper" },
  { id: "ORD-2840", t: "09:58:12", sym: "068270", side: "BUY",  qty: 1, status: "FILLED",   px: "178,300", note: "paper" },
  { id: "ORD-2839", t: "09:45:03", sym: "207940", side: "SELL", qty: 1, status: "REJECTED", px: "—",        note: "리스크 한도" },
  { id: "ORD-2838", t: "09:31:22", sym: "051910", side: "SELL", qty: 1, status: "PENDING",  px: "348,000", note: "shadow" },
];

const AUDIT = [
  { t: "10:03:48", level: "INFO",  src: "sync",   msg: "동기화 완료 · 32 시계열 점 · 4 신호" },
  { t: "10:02:41", level: "INFO",  src: "order",  msg: "주문 체결 (paper) · 000660 BUY 2" },
  { t: "09:45:03", level: "WARN",  src: "risk",   msg: "주문 거절: 일일 한도 초과 (6/6)" },
  { t: "09:30:01", level: "INFO",  src: "agent",  msg: "사이클 시작 (#412) · idle_waiting → analyzing" },
  { t: "09:29:55", level: "INFO",  src: "system", msg: "워커 일시중지 후 재개" },
  { t: "09:00:00", level: "INFO",  src: "system", msg: "운영 단계: shadow / 긴급정지: 활성" },
];

/* ============================================================
   DashboardPage
   ============================================================ */
const DashboardPage = ({ ctx }) => {
  return (
    <>
      <header style={{ marginBottom: 18 }}>
        <div className="row" style={{ gap: 10, marginBottom: 8 }}>
          <span className="badge badge--gray" style={{ fontSize: 10.5, letterSpacing: "0.12em" }}>ALPHA-GEN · OPS CONSOLE</span>
        </div>
        <h1 className="h-title">운영 현황을 한눈에 보는 트레이딩 콘솔</h1>
        <p className="h-sub">핵심 지표와 차트를 대시보드에 모아두었습니다. 상세 데이터는 각 메뉴에서 확인하세요.</p>
      </header>

      {/* 4 metric cards */}
      <div className="grid-4" style={{ marginBottom: 14 }}>
        <Metric
          label="총자산"
          value={ctx.totalAssets.toLocaleString()}
          unit="원"
          sub={<><span className={ctx.pnlPct >= 0 ? "" : ""} style={{ color: ctx.pnlPct >= 0 ? "var(--green-600)" : "var(--red-600)" }}>
            {ctx.pnlPct >= 0 ? "+" : ""}{ctx.pnlPct.toFixed(2)}%
          </span> · 기준선 대비</>}
        />
        <Metric
          label="현금"
          value={ctx.cash.toLocaleString()}
          unit="원"
          sub={<><span className="muted">가용 비중 </span>{((ctx.cash / ctx.totalAssets) * 100).toFixed(1)}%</>}
        />
        <Metric
          label="워커 상태"
          tone={ctx.worker === "STOPPED" ? "danger" : null}
          value={ctx.worker === "STOPPED" ? "STOPPED" : ctx.worker === "RUNNING" ? "RUNNING" : "대기 중"}
          right={ctx.worker === "STOPPED"
            ? <Badge tone="red" solid>중지됨</Badge>
            : ctx.worker === "RUNNING"
            ? <Badge tone="green" dot>실행 중</Badge>
            : <Badge tone="gray" dot>대기</Badge>}
          sub={<>마지막 실행 <span className="mono">432분 09초</span> 전</>}
        />
        <Metric
          label="리스크 상태"
          value="0.00"
          unit="%"
          right={<Badge tone="blue" dot>휴면 모드</Badge>}
          sub={<>일일 한도 <span className="mono">6/6</span> · 시세 120s</>}
        />
      </div>

      {/* Charts row + Right rail */}
      <div className="dash-grid">
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Card
            eyebrow="EQUITY"
            title="총자산 추이"
            right={
              <div className="row" style={{ gap: 6 }}>
                <button className="btn btn--sm">1D</button>
                <button className="btn btn--sm btn--ghost" style={{ background: "var(--bg-tertiary)" }}>1W</button>
                <button className="btn btn--sm btn--ghost">1M</button>
              </div>
            }
          >
            <EquityChart data={EQUITY.data} baseline={EQUITY.baseline} width={780} height={236} />
          </Card>

          <div className="grid-2">
            <Card
              eyebrow="SIGNAL MIX"
              title="시그널 분포"
              right={<span className="muted" style={{ fontSize: 12 }}>총 {SIGNAL_ROWS.reduce((a,b)=>a+b.value,0)}건</span>}
            >
              <SignalBars rows={SIGNAL_ROWS} />
            </Card>
            <Card
              eyebrow="LATEST CYCLE"
              title="최근 사이클"
              right={<Badge tone="green" dot>완료</Badge>}
            >
              <dl className="kv">
                <dt>사이클 ID</dt>           <dd>#412</dd>
                <dt>실행 시각</dt>           <dd>05. 27. 오후 02:51:39</dd>
                <dt>분석 종목</dt>           <dd>23 개</dd>
                <dt>생성 시그널</dt>         <dd>4 건 (BUY 1 · SELL 1)</dd>
                <dt>주문 발행</dt>           <dd>0 건 <span className="muted">(shadow)</span></dd>
                <dt>다음 실행</dt>           <dd>05. 27. 오전 02:09:02</dd>
              </dl>
            </Card>
          </div>
        </div>

        {/* Right rail */}
        <aside className="rail">
          <RailQuickActions ctx={ctx} />
          <RailAutomation />
          <RailSafety ctx={ctx} />
          <RailOrderTest ctx={ctx} />
        </aside>
      </div>
    </>
  );
};

/* ============================================================
   Right rail panels
   ============================================================ */
const RailQuickActions = ({ ctx }) => {
  const isRunning = ctx.worker === "RUNNING";
  return (
    <div className="rail-card">
      <div className="rail-card__head">
        <div className="rail-card__title">빠른 실행</div>
        <span className="kbd">Q</span>
      </div>
      <div className="grid-2" style={{ gap: 8 }}>
        <button className="btn" onClick={() => ctx.toast("분석을 새로 시작합니다")}>
          <Icon name="refresh" size={14} />
          분석 새로고침
        </button>
        <button className="btn" onClick={() => ctx.toast("에이전트 1회 사이클 실행")}>
          <Icon name="bolt" size={14} />
          에이전트 1회
        </button>
        <button
          className={"btn " + (isRunning ? "" : "btn--primary")}
          onClick={() => { ctx.setWorker("RUNNING"); ctx.toast("워커가 시작되었습니다"); }}
          disabled={isRunning}
        >
          <Icon name="play" size={12} />
          워커 시작
        </button>
        <button
          className="btn"
          onClick={() => { ctx.setWorker("STOPPED"); ctx.toast("워커가 중지되었습니다"); }}
          disabled={ctx.worker === "STOPPED"}
        >
          <Icon name="pause" size={12} />
          워커 중지
        </button>
      </div>
    </div>
  );
};

const RailAutomation = () => (
  <div className="rail-card">
    <div className="rail-card__head">
      <div className="rail-card__title">자동화 상태</div>
      <Badge tone="gray" dot>대기 중</Badge>
    </div>
    <dl className="kv">
      <dt>현재 상태</dt>         <dd>idle_waiting</dd>
      <dt>마지막 실행</dt>       <dd>14:51:39 · <span className="muted">432분 전</span></dd>
      <dt>다음 실행 예정</dt>    <dd>02:09:02 <span className="muted">(+19h)</span></dd>
      <dt>최근 결과</dt>         <dd>1회 · 시그널 4건</dd>
    </dl>
  </div>
);

const RailSafety = ({ ctx }) => {
  const [pending, setPending] = useState_d(false);
  const [estop, setEstop] = useState_d(true);
  return (
    <div className="rail-card">
      <div className="rail-card__head">
        <div className="rail-card__title">운영 안전장치</div>
        {estop
          ? <Badge tone="red" dot>긴급정지 활성</Badge>
          : <Badge tone="green" dot>정상</Badge>}
      </div>

      <div className="field" style={{ marginBottom: 12 }}>
        <span className="field__label">운영 단계</span>
        <StagePills value={ctx.stage} onChange={ctx.setStage} />
      </div>

      <div className="grid-2" style={{ gap: 8, marginBottom: 10 }}>
        <div style={{ background: "var(--bg-subtle)", padding: "10px 12px", borderRadius: 8 }}>
          <div className="muted" style={{ fontSize: 11.5 }}>주문 한도</div>
          <div style={{ fontWeight: 550, fontSize: 14 }}>6 건/일</div>
          <div className="muted" style={{ fontSize: 11.5 }}>신호 900s · 시세 120s</div>
        </div>
        <div style={{ background: "var(--bg-subtle)", padding: "10px 12px", borderRadius: 8 }}>
          <div className="muted" style={{ fontSize: 11.5 }}>최대 손실 한도</div>
          <div style={{ fontWeight: 550, fontSize: 14 }}>-2.50%</div>
          <div className="muted" style={{ fontSize: 11.5 }}>일일 / 자동 정지</div>
        </div>
      </div>

      <div className="field" style={{ marginBottom: 10 }}>
        <span className="field__label">긴급 정지 사유</span>
        <input className="input" defaultValue="운영자 수동 정지" />
      </div>

      {estop ? (
        <button className="btn btn--block" onClick={() => { setEstop(false); ctx.toast("긴급 정지가 해제되었습니다"); }}>
          긴급 정지 해제
        </button>
      ) : (
        <button className="btn btn--danger btn--block" onClick={() => setPending(true)}>
          <Icon name="warn" size={14} />
          긴급 정지 활성화
        </button>
      )}

      <ConfirmDialog
        open={pending}
        title="긴급 정지를 활성화하시겠습니까?"
        body="모든 대기 중인 주문이 즉시 취소되고, 워커가 정지됩니다. 해제 전까지 신규 주문은 발행되지 않습니다."
        danger
        confirmText="긴급 정지 활성화"
        onCancel={() => setPending(false)}
        onConfirm={() => { setEstop(true); setPending(false); ctx.setWorker("STOPPED"); ctx.toast("긴급 정지가 활성화되었습니다"); }}
      />
    </div>
  );
};

const RailOrderTest = ({ ctx }) => {
  const [sym, setSym] = useState_d("005930");
  const [side, setSide] = useState_d("BUY");
  const [qty, setQty] = useState_d(1);
  return (
    <div className="rail-card">
      <div className="rail-card__head">
        <div className="rail-card__title">주문 테스트</div>
        <Badge tone="blue" dot>{ctx.stage === "live" ? "Live" : ctx.stage === "paper" ? "Paper" : "Shadow"}</Badge>
      </div>
      <div className="grid-2" style={{ gap: 10, marginBottom: 10 }}>
        <div className="field">
          <span className="field__label">심볼</span>
          <input className="input" value={sym} onChange={e => setSym(e.target.value)} />
        </div>
        <div className="field">
          <span className="field__label">세션</span>
          <select className="select"><option>KR</option><option>US</option></select>
        </div>
        <div className="field">
          <span className="field__label">방향</span>
          <select className="select" value={side} onChange={e => setSide(e.target.value)}>
            <option>BUY</option><option>SELL</option>
          </select>
        </div>
        <div className="field">
          <span className="field__label">수량</span>
          <input className="input" type="number" value={qty} onChange={e => setQty(+e.target.value)} />
        </div>
      </div>
      <button
        className="btn btn--accent btn--block"
        onClick={() => ctx.toast(`${ctx.stage === "live" ? "Live" : "Paper"} 주문 발행 · ${side} ${sym} × ${qty}`)}
      >
        {ctx.stage === "live" ? "Live" : "Paper"} 주문 발행
      </button>
    </div>
  );
};

/* ============================================================
   Other pages
   ============================================================ */
const PortfolioPage = () => (
  <>
    <header style={{ marginBottom: 18 }}>
      <h1 className="h-title">포트폴리오</h1>
      <p className="h-sub">현재 보유 포지션과 비중을 확인하세요.</p>
    </header>
    <div className="grid-4" style={{ marginBottom: 14 }}>
      <Metric label="평가금액" value="10,000,000" unit="원" sub={<span className="muted">+0.00% vs 기준선</span>} />
      <Metric label="현금" value="10,000,000" unit="원" sub={<span className="muted">100.0% 비중</span>} />
      <Metric label="보유 종목" value="0" unit="개" sub={<span className="muted">전 거래일 0</span>} />
      <Metric label="미실현 손익" value="0" unit="원" sub={<span className="muted">— 휴면 상태</span>} />
    </div>
    <Card title="보유 종목" eyebrow="POSITIONS" right={<Badge tone="gray">현재 0건</Badge>}>
      <div style={{ padding: "40px 0", textAlign: "center", color: "var(--ink-3)" }}>
        <div style={{ fontSize: 13.5 }}>보유 종목이 없습니다.</div>
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>워커가 활성화되고 주문이 체결되면 여기 표시됩니다.</div>
      </div>
    </Card>
  </>
);

const SignalsPage = () => (
  <>
    <header style={{ marginBottom: 18 }}>
      <h1 className="h-title">시그널</h1>
      <p className="h-sub">최근 사이클에서 생성된 시그널과 점수를 확인하세요.</p>
    </header>
    <div className="grid-4" style={{ marginBottom: 14 }}>
      <Metric label="총 시그널" value="20" unit="건" sub={<span className="muted">최근 사이클</span>} />
      <Metric label="BUY 후보" value="4" unit="건" right={<Badge tone="green" dot>강세</Badge>} sub={<span className="muted">평균 점수 0.78</span>} />
      <Metric label="SELL 후보" value="2" unit="건" right={<Badge tone="red" dot>약세</Badge>} sub={<span className="muted">평균 점수 0.28</span>} />
      <Metric label="WATCH" value="14" unit="건" sub={<span className="muted">관망</span>} />
    </div>
    <Card title="시그널 리스트" eyebrow="LATEST CYCLE #412">
      <div style={{ margin: "-4px -4px 0" }}>
        <table className="table">
          <thead>
            <tr>
              <th>종목</th><th>판정</th>
              <th className="num">점수</th><th className="num">현재가</th><th className="num">전일대비</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {SIGNALS_LIST.map(s => (
              <tr key={s.ticker}>
                <td>
                  <div style={{ fontWeight: 500 }}>{s.name}</div>
                  <div className="mono muted">{s.ticker}</div>
                </td>
                <td>
                  {s.side === "BUY"   && <Badge tone="green" dot>BUY 후보</Badge>}
                  {s.side === "SELL"  && <Badge tone="red"   dot>SELL 후보</Badge>}
                  {s.side === "WATCH" && <Badge tone="gray"  dot>WATCH</Badge>}
                </td>
                <td className="num mono">{s.score.toFixed(2)}</td>
                <td className="num">{s.price}</td>
                <td className={"num " + (s.chg >= 0 ? "num-pos" : "num-neg")}>
                  {s.chg >= 0 ? "+" : ""}{s.chg.toFixed(2)}%
                </td>
                <td className="num">
                  <button className="btn btn--sm btn--ghost">상세</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  </>
);

const OrdersPage = ({ ctx }) => (
  <>
    <header style={{ marginBottom: 18 }}>
      <h1 className="h-title">주문</h1>
      <p className="h-sub">최근 발행된 주문과 상태입니다.</p>
    </header>
    <Card
      title="최근 주문"
      eyebrow="ORDERS"
      right={
        <div className="row" style={{ gap: 6 }}>
          <Badge tone="gray">오늘 {ORDERS.length}건</Badge>
          <button className="btn btn--sm">필터</button>
        </div>
      }
    >
      <table className="table">
        <thead>
          <tr>
            <th>주문 ID</th><th>시각</th><th>심볼</th><th>방향</th>
            <th className="num">수량</th><th className="num">체결가</th>
            <th>상태</th><th>비고</th>
          </tr>
        </thead>
        <tbody>
          {ORDERS.map(o => (
            <tr key={o.id}>
              <td className="mono">{o.id}</td>
              <td className="mono muted">{o.t}</td>
              <td className="mono">{o.sym}</td>
              <td>
                {o.side === "BUY"
                  ? <Badge tone="green">BUY</Badge>
                  : <Badge tone="red">SELL</Badge>}
              </td>
              <td className="num mono">{o.qty}</td>
              <td className="num mono">{o.px}</td>
              <td>
                {o.status === "FILLED"   && <Badge tone="green" dot>FILLED</Badge>}
                {o.status === "PENDING"  && <Badge tone="amber" dot>PENDING</Badge>}
                {o.status === "REJECTED" && <Badge tone="red"   dot>REJECTED</Badge>}
              </td>
              <td className="muted" style={{ fontSize: 12.5 }}>{o.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  </>
);

const BacktestsPage = () => (
  <>
    <header style={{ marginBottom: 18 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="h-title">백테스트</h1>
          <p className="h-sub">최근 실행한 전략 백테스트 결과입니다.</p>
        </div>
        <button className="btn btn--primary"><Icon name="play" size={12}/> 최근 전략 백테스트</button>
      </div>
    </header>
    <div className="row" style={{ gap: 8, marginBottom: 14 }}>
      <Badge tone="gray">최근 {BACKTESTS.length}회</Badge>
      <Badge tone="green" dot>최신 수익률 +{BACKTESTS[0].ret.toFixed(2)}%</Badge>
      <Badge tone="gray">평균 승률 {Math.round(BACKTESTS.reduce((a,b)=>a+b.win,0) / BACKTESTS.length)}%</Badge>
    </div>
    <Card>
      <table className="table">
        <thead>
          <tr>
            <th>실행 시각</th>
            <th className="num">수익률</th>
            <th className="num">승률</th>
            <th className="num">거래 수</th>
            <th className="num">총 손익</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {BACKTESTS.map(b => (
            <tr key={b.id}>
              <td>{b.when}</td>
              <td className="num">
                {b.ret >= 0
                  ? <Badge tone="green">+{b.ret.toFixed(2)}%</Badge>
                  : <Badge tone="red">{b.ret.toFixed(2)}%</Badge>}
              </td>
              <td className="num mono">{b.win.toFixed(1)}%</td>
              <td className="num mono">{b.trades}건</td>
              <td className={"num " + (b.pnl >= 0 ? "num-pos" : "num-neg")}>
                {b.pnl >= 0 ? "+" : ""}{b.pnl.toLocaleString()}원
              </td>
              <td className="num">
                <button className="btn btn--sm btn--ghost">리포트</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  </>
);

const AuditPage = () => (
  <>
    <header style={{ marginBottom: 18 }}>
      <h1 className="h-title">감사 로그</h1>
      <p className="h-sub">시스템 이벤트와 운영 행위 기록입니다.</p>
    </header>
    <Card>
      <table className="table">
        <thead>
          <tr><th style={{ width: 90 }}>시각</th><th style={{ width: 90 }}>레벨</th><th style={{ width: 90 }}>소스</th><th>메시지</th></tr>
        </thead>
        <tbody>
          {AUDIT.map((a, i) => (
            <tr key={i}>
              <td className="mono muted">{a.t}</td>
              <td>
                {a.level === "WARN"  && <Badge tone="amber" dot>WARN</Badge>}
                {a.level === "INFO"  && <Badge tone="gray"  dot>INFO</Badge>}
                {a.level === "ERROR" && <Badge tone="red"   dot>ERROR</Badge>}
              </td>
              <td className="mono">{a.src}</td>
              <td>{a.msg}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  </>
);

const SystemPage = ({ ctx }) => (
  <>
    <header style={{ marginBottom: 18 }}>
      <h1 className="h-title">시스템</h1>
      <p className="h-sub">백엔드 연결, 데이터 소스, 환경 변수 상태입니다.</p>
    </header>
    <div className="grid-2" style={{ marginBottom: 14 }}>
      <Card title="런타임" eyebrow="RUNTIME">
        <dl className="kv">
          <dt>FastAPI</dt>         <dd>0.110.2 · <Badge tone="green" dot>healthy</Badge></dd>
          <dt>SQLite</dt>          <dd>alpha_gen.sqlite3 · 14.2 MB</dd>
          <dt>워커 PID</dt>        <dd className="mono">—</dd>
          <dt>업타임</dt>          <dd>7h 12m</dd>
        </dl>
      </Card>
      <Card title="데이터 소스" eyebrow="ADAPTERS">
        <dl className="kv">
          <dt>KIS Paper</dt>       <dd><Badge tone="green" dot>connected</Badge></dd>
          <dt>News (Naver)</dt>    <dd><Badge tone="green" dot>connected</Badge></dd>
          <dt>Yahoo Finance</dt>   <dd><Badge tone="blue" dot>fallback</Badge></dd>
          <dt>토큰 만료</dt>       <dd>2026-05-28 06:00</dd>
        </dl>
      </Card>
    </div>
    <Card title="긴급 운영 액션" eyebrow="DANGER ZONE">
      <p className="muted" style={{ marginTop: 0 }}>다음 액션은 실행 즉시 반영되며 되돌릴 수 없습니다.</p>
      <div className="row" style={{ gap: 8 }}>
        <button className="btn">캐시 초기화</button>
        <button className="btn">토큰 재발급</button>
        <button className="btn btn--danger" onClick={() => ctx.toast("DB 스냅샷이 생성되었습니다")}>DB 스냅샷 후 초기화</button>
      </div>
    </Card>
  </>
);

Object.assign(window, {
  DashboardPage, PortfolioPage, SignalsPage, OrdersPage,
  BacktestsPage, AuditPage, SystemPage,
});

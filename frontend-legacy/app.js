const jsonHeaders = { "Content-Type": "application/json" };
const ACTIVE_REFRESH_MS = 3000;
const IDLE_REFRESH_MS = 10000;

const $ = (selector) => document.querySelector(selector);
let refreshTimer = null;
let refreshInFlight = false;

function currency(value) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function percent(value) {
  const numeric = Number(value || 0);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function toneClass(value) {
  const numeric = Number(value || 0);
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

function badgeClassByStatus(status) {
  const normalized = String(status || "").toLowerCase();
  if (["filled", "running", "ready", "ok"].includes(normalized)) return "success";
  if (["rejected", "error", "stopped"].includes(normalized)) return "danger";
  return "warning";
}

function badgeClassBySeverity(severity) {
  const normalized = String(severity || "").toLowerCase();
  if (["critical", "danger"].includes(normalized)) return "danger";
  if (normalized === "warning") return "warning";
  return "success";
}

function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return "없음";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatCompactDateTime(value) {
  const date = parseDate(value);
  if (!date) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function shortText(value, maxLength = 42) {
  const normalized = String(value ?? "").trim();
  if (normalized.length <= maxLength) return normalized || "-";
  return `${normalized.slice(0, maxLength - 1)}…`;
}

function formatRelative(value) {
  const date = parseDate(value);
  if (!date) return "없음";
  const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
  if (diffSec >= 0) {
    if (diffSec < 60) return `${diffSec}초 후`;
    const min = Math.floor(diffSec / 60);
    const sec = diffSec % 60;
    return `${min}분 ${sec}초 후`;
  }
  const ago = Math.abs(diffSec);
  if (ago < 60) return `${ago}초 전`;
  const min = Math.floor(ago / 60);
  const sec = ago % 60;
  return `${min}분 ${sec}초 전`;
}

function setSyncState(label, note, tone = "warning") {
  const statusEl = $("#sync-status");
  const noteEl = $("#sync-note");
  statusEl.textContent = label;
  statusEl.className = `badge ${tone}`;
  noteEl.textContent = note;
}

function scheduleRefresh(workerRunning) {
  window.clearTimeout(refreshTimer);
  const delay = workerRunning ? ACTIVE_REFRESH_MS : IDLE_REFRESH_MS;
  refreshTimer = window.setTimeout(() => {
    loadDashboard(true).catch((error) => {
      setSyncState("동기화 오류", error.message, "danger");
    });
  }, delay);
}

function renderEquityChart(equity = []) {
  const target = $("#equity-chart");
  if (!equity.length) {
    target.innerHTML = `<div class="chart-empty">표시할 자산 히스토리가 아직 없습니다.</div>`;
    return;
  }

  const values = equity.map((item) => Number(item.total_asset || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const width = 640;
  const height = 190;
  const left = 18;
  const right = 18;
  const top = 18;
  const bottom = 28;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;

  const points = values.map((value, index) => {
    const x = left + (values.length === 1 ? chartWidth / 2 : (chartWidth * index) / (values.length - 1));
    const y = top + chartHeight - (((value - min) / range) * chartHeight);
    return [x, y];
  });

  const linePath = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1][0]} ${top + chartHeight} L ${points[0][0]} ${top + chartHeight} Z`;

  const last = values[values.length - 1];
  const first = values[0];
  const diffPct = first ? (((last - first) / first) * 100).toFixed(2) : "0.00";

  target.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="총자산 추이">
      <line class="chart-gridline" x1="${left}" y1="${top}" x2="${width - right}" y2="${top}" />
      <line class="chart-gridline" x1="${left}" y1="${top + chartHeight / 2}" x2="${width - right}" y2="${top + chartHeight / 2}" />
      <line class="chart-gridline" x1="${left}" y1="${top + chartHeight}" x2="${width - right}" y2="${top + chartHeight}" />
      <path class="chart-area" d="${areaPath}" />
      <path class="chart-line" d="${linePath}" />
      ${points.map(([x, y], index) => `<circle class="chart-point" cx="${x}" cy="${y}" r="${index === points.length - 1 ? 4 : 2.5}" />`).join("")}
      <text class="chart-label" x="${left}" y="${height - 8}">시작 ${currency(first)}원</text>
      <text class="chart-label" x="${width - right}" y="${height - 8}" text-anchor="end">현재 ${currency(last)}원 (${diffPct > 0 ? "+" : ""}${diffPct}%)</text>
    </svg>
  `;
}

function renderSignalChart(signals = []) {
  const target = $("#signal-chart");
  if (!signals.length) {
    target.innerHTML = `<div class="chart-empty">시그널이 쌓이면 분포 차트가 나타납니다.</div>`;
    return;
  }

  const buyCount = signals.filter((item) => item.buy_signal).length;
  const watchCount = Math.max(signals.length - buyCount, 0);
  const maxCount = Math.max(buyCount, watchCount, 1);
  const rows = [
    { label: "BUY 후보", value: buyCount, css: "bar-fill-buy" },
    { label: "WATCH", value: watchCount, css: "bar-fill-watch" },
  ];

  target.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 640 190" preserveAspectRatio="none" role="img" aria-label="시그널 분포">
      ${rows.map((row, index) => {
        const y = 30 + (index * 68);
        const barWidth = (row.value / maxCount) * 410;
        return `
          <text class="chart-label" x="18" y="${y - 10}">${row.label}</text>
          <rect class="bar-track" x="18" y="${y}" rx="12" ry="12" width="410" height="22" />
          <rect class="${row.css}" x="18" y="${y}" rx="12" ry="12" width="${Math.max(barWidth, row.value ? 16 : 0)}" height="22" />
          <text class="chart-label" x="446" y="${y + 15}">${row.value}건</text>
        `;
      }).join("")}
      <text class="chart-label" x="18" y="172">전체 시그널 ${signals.length}건</text>
      <text class="chart-label" x="622" y="172" text-anchor="end">평균 감성 ${(
        signals.reduce((sum, item) => sum + Number(item.sentiment_score || 0), 0) / signals.length
      ).toFixed(2)}</text>
    </svg>
  `;
}

function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.remove("hidden");
  el.style.borderColor = isError ? "rgba(239,68,68,0.5)" : "rgba(16,185,129,0.4)";
  window.clearTimeout(window.__toastTimer);
  window.__toastTimer = window.setTimeout(() => el.classList.add("hidden"), 3000);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.message || "API 요청 실패");
  }
  return data;
}

function renderPortfolio(payload) {
  $("#metric-total-asset").textContent = `${currency(payload.total_asset)}원`;
  $("#metric-cash").textContent = `${currency(payload.cash)}원`;
  $("#portfolio-count").textContent = `${payload.positions.length} positions`;

  const risk = payload.risk || {};
  $("#portfolio-overview").innerHTML = `
    <div class="mini-stat">
      <div class="mini-stat-label">보유 포지션</div>
      <div class="mini-stat-value">${payload.positions.length}개</div>
    </div>
    <div class="mini-stat">
      <div class="mini-stat-label">드로우다운</div>
      <div class="mini-stat-value ${toneClass(risk.drawdown_pct)}">${percent(risk.drawdown_pct || 0)}</div>
    </div>
    <div class="mini-stat">
      <div class="mini-stat-label">손절 감시</div>
      <div class="mini-stat-value">${risk.stop_loss_count || 0}건</div>
    </div>
    <div class="mini-stat">
      <div class="mini-stat-label">운영 상태</div>
      <div class="mini-stat-value">${risk.sleep_mode ? "휴면" : "활성"}</div>
    </div>
  `;

  const rows = payload.positions.map((item) => {
    const pnlPct = item.avg_price ? (((item.last_price - item.avg_price) / item.avg_price) * 100) : 0;
    return `
      <tr>
        <td>${escapeHtml(item.stock_name)}</td>
        <td>${escapeHtml(item.stock_code)}</td>
        <td>${escapeHtml(item.session)}</td>
        <td>${escapeHtml(item.qty)}</td>
        <td>${currency(item.avg_price)}</td>
        <td>${currency(item.last_price)}</td>
        <td class="${toneClass(pnlPct)}">${percent(pnlPct)}</td>
      </tr>
    `;
  }).join("");

  $("#portfolio-table").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>종목</th>
          <th>코드</th>
          <th>세션</th>
          <th>수량</th>
          <th>평단</th>
          <th>현재가</th>
          <th>손익률</th>
        </tr>
      </thead>
      <tbody>${rows || `<tr><td colspan="7"><div class="empty-state">아직 보유 포지션이 없습니다. 좌측 주문 테스트나 에이전트 실행으로 흐름을 시작할 수 있습니다.</div></td></tr>`}</tbody>
    </table>
  `;
}

function renderSignals(payload) {
  const signals = payload.signals || [];
  if (!signals.length) {
    $("#signals-list").innerHTML = `<div class="list-card">아직 저장된 시그널이 없습니다.</div>`;
    return;
  }

  const buyCount = signals.filter((signal) => signal.buy_signal).length;
  const avgSentiment = signals.reduce((sum, signal) => sum + Number(signal.sentiment_score || 0), 0) / signals.length;
  const rows = signals.map((signal) => `
    <tr>
      <td>
        <div class="cell-title">${escapeHtml(signal.stock_name)} (${escapeHtml(signal.stock_code)})</div>
        <div class="cell-sub">${escapeHtml(shortText(signal.technical_reason || "기술 신호 사유 없음"))}</div>
      </td>
      <td><span class="pill ${String(signal.session).toLowerCase()}">${escapeHtml(signal.session)}</span></td>
      <td><span class="badge ${signal.buy_signal ? "success" : "warning"}">${signal.buy_signal ? "BUY" : "WATCH"}</span></td>
      <td class="${toneClass(signal.sentiment_score)}">${escapeHtml(signal.sentiment_label)} ${signal.sentiment_score > 0 ? "+" : ""}${escapeHtml(String(signal.sentiment_score))}</td>
      <td>${currency(signal.current_price)}원</td>
      <td>${signal.technical_signal ? "통과" : "보류"}</td>
    </tr>
  `).join("");

  $("#signals-list").innerHTML = `
    <div class="list-toolbar">
      <span class="badge">전체 ${signals.length}건</span>
      <span class="badge success">BUY ${buyCount}건</span>
      <span class="badge warning">WATCH ${Math.max(signals.length - buyCount, 0)}건</span>
      <span class="badge">평균 감성 ${avgSentiment.toFixed(2)}</span>
    </div>
    <div class="dense-table-wrap">
      <table class="dense-table">
        <thead>
          <tr>
            <th>종목</th>
            <th>세션</th>
            <th>액션</th>
            <th>감성</th>
            <th>현재가</th>
            <th>기술</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderOrders(payload) {
  const orders = payload.orders || [];
  if (!orders.length) {
    $("#orders-list").innerHTML = `<div class="list-card">주문 이력이 없습니다.</div>`;
    return;
  }

  const filledCount = orders.filter((order) => String(order.status).toLowerCase() === "filled").length;
  const rejectedCount = orders.filter((order) => String(order.status).toLowerCase() === "rejected").length;
  const realizedTotal = orders.reduce((sum, order) => sum + Number(order.realized_pnl || 0), 0);
  const rows = orders.map((order) => `
    <tr>
      <td>
        <div class="cell-title">${escapeHtml(order.stock_name || order.stock_code)}</div>
        <div class="cell-sub">${escapeHtml(order.stock_code)} · <span class="cell-note">${escapeHtml(shortText(order.message || "주문 메시지 없음"))}</span></div>
      </td>
      <td>
        <div class="stacked-badges">
          <span class="side-badge ${escapeHtml(String(order.side).toLowerCase())}">${escapeHtml(String(order.side).toUpperCase())}</span>
          <span class="pill ${String(order.session).toLowerCase()}">${escapeHtml(order.session)}</span>
        </div>
      </td>
      <td><span class="badge ${badgeClassByStatus(order.status)}">${escapeHtml(order.status)}</span></td>
      <td>${currency(order.executed_price || order.requested_price)}원<div class="cell-sub">${escapeHtml(String(order.qty))}주 · 시도 ${escapeHtml(String(order.attempt_count || 0))}회</div></td>
      <td class="${toneClass(order.realized_pnl)}">${order.realized_pnl == null ? "-" : `${currency(order.realized_pnl)}원`}</td>
      <td>${formatCompactDateTime(order.created_at)}</td>
    </tr>
  `).join("");

  $("#orders-list").innerHTML = `
    <div class="list-toolbar">
      <span class="badge">전체 ${orders.length}건</span>
      <span class="badge success">체결 ${filledCount}건</span>
      <span class="badge danger">거절 ${rejectedCount}건</span>
      <span class="badge ${realizedTotal >= 0 ? "success" : "danger"}">실현손익 ${realizedTotal >= 0 ? "+" : ""}${currency(realizedTotal)}원</span>
    </div>
    <div class="dense-table-wrap">
      <table class="dense-table">
        <thead>
          <tr>
            <th>종목</th>
            <th>구분</th>
            <th>상태</th>
            <th>가격/수량</th>
            <th>실현손익</th>
            <th>시각</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderBacktests(payload) {
  const runs = payload.runs || [];
  if (!runs.length) {
    $("#backtests-list").innerHTML = `<div class="list-card">백테스트 기록이 없습니다.</div>`;
    return;
  }

  const rows = runs.map((run) => `
    <tr>
      <td>${formatCompactDateTime(run.created_at)}</td>
      <td class="${Number(run.summary.total_return_pct) >= 0 ? "positive" : "negative"}">${percent(run.summary.total_return_pct)}</td>
      <td>${Number(run.summary.win_rate).toFixed(1)}%</td>
      <td>${escapeHtml(String(run.summary.trade_count))}건</td>
      <td class="${toneClass(run.summary.gross_pnl)}">${currency(run.summary.gross_pnl)}원</td>
    </tr>
  `).join("");

  $("#backtests-list").innerHTML = `
    <div class="list-toolbar">
      <span class="badge">최근 ${runs.length}회</span>
      <span class="badge ${Number(runs[0].summary.total_return_pct) >= 0 ? "success" : "danger"}">최신 수익률 ${percent(runs[0].summary.total_return_pct)}</span>
    </div>
    <div class="dense-table-wrap">
      <table class="dense-table">
        <thead>
          <tr>
            <th>실행 시각</th>
            <th>수익률</th>
            <th>승률</th>
            <th>거래 수</th>
            <th>총 손익</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderSafety(payload) {
  const policy = payload.policy || {};
  const stop = policy.emergency_stop || {};
  const limits = policy.limits || {};

  $("#stage-select").value = String(policy.stage || "paper");
  $("#safety-status").innerHTML = `
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">운영 단계</div>
      <div class="worker-monitor-value">${escapeHtml(policy.stage || "-")}</div>
      <div class="worker-monitor-note">자동 주문 ${policy.auto_orders_enabled ? "활성" : "비활성"} · 실거래 ${policy.live_orders_enabled ? "활성" : "비활성"}</div>
    </div>
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">긴급 정지</div>
      <div class="worker-monitor-value ${stop.enabled ? "negative" : "positive"}">${stop.enabled ? "활성" : "해제"}</div>
      <div class="worker-monitor-note">${escapeHtml(stop.reason || "정상 운영 중")}</div>
    </div>
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">주문 제한</div>
      <div class="worker-monitor-value">${escapeHtml(String(limits.live_max_orders_per_day ?? "-"))}건/일</div>
      <div class="worker-monitor-note">신호 ${escapeHtml(String(limits.signal_staleness_sec ?? "-"))}초 · 시세 ${escapeHtml(String(limits.quote_staleness_sec ?? "-"))}초</div>
    </div>
  `;
}

function renderAudit(payload) {
  const events = payload.events || [];
  if (!events.length) {
    $("#audit-list").innerHTML = `<div class="list-card">감사 이벤트가 아직 없습니다.</div>`;
    return;
  }

  $("#audit-list").innerHTML = `
    <div class="audit-list">
      ${events.map((event) => `
        <div class="audit-card ${escapeHtml(String(event.severity || "info").toLowerCase())}">
          <div class="audit-top">
            <div>
              <div class="audit-title">${escapeHtml(event.event_type)}</div>
              <div class="audit-meta">${formatCompactDateTime(event.created_at)} · ${escapeHtml(event.scope || "-")}${event.session ? ` · ${escapeHtml(event.session)}` : ""}</div>
            </div>
            <span class="badge ${badgeClassBySeverity(event.severity)}">${escapeHtml(event.severity || "info")}</span>
          </div>
          <div class="audit-message">${escapeHtml(event.message || "-")}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderSystem(payload, policy) {
  const workerRunning = Boolean(payload.worker.running);
  $("#system-summary").textContent = payload.diagnostics.summary;
  $("#system-summary").className = `badge ${badgeClassByStatus(payload.diagnostics.summary)}`;
  $("#metric-worker").textContent = workerRunning ? "RUNNING" : "STOPPED";
  $("#metric-worker").className = workerRunning ? "running" : "stopped";

  const missingConfig = payload.diagnostics.integrations.missing_config || [];
  const modeText = payload.config.mock_mode
    ? `Mock (${payload.config.mock_mode_reason || "manual"})`
    : `${payload.config.operating_stage || "paper"}${payload.config.allow_live_trading ? " · live enabled" : ""}`;

  $("#runtime-badges").innerHTML = `
    <span class="badge ${payload.config.mock_mode ? "warning" : "success"}">${escapeHtml(modeText)}</span>
    <span class="badge ${policy.shadow_mode ? "warning" : policy.live_orders_enabled ? "danger" : "success"}">${escapeHtml(policy.stage || payload.config.operating_stage || "paper")}</span>
    <span class="badge ${workerRunning ? "success live" : "danger"}">${workerRunning ? "워커 실행 중" : "워커 중지"}</span>
    <span class="badge ${policy.emergency_stop?.enabled ? "danger" : "success"}">${policy.emergency_stop?.enabled ? "긴급 정지 활성" : "긴급 정지 해제"}</span>
    <span class="badge ${missingConfig.length ? "warning" : "success"}">${missingConfig.length ? "설정 보완 필요" : "설정 완료"}</span>
  `;

  const lastResult = payload.worker.last_result || {};
  $("#worker-monitor").innerHTML = `
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">현재 상태</div>
      <div class="worker-monitor-value">${workerRunning ? "자동 실행 중" : "대기 중"}</div>
      <div class="worker-monitor-note">${escapeHtml(payload.worker.current_status || "idle")}</div>
    </div>
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">마지막 실행</div>
      <div class="worker-monitor-value">${formatDateTime(payload.worker.last_cycle_at)}</div>
      <div class="worker-monitor-note">${formatRelative(payload.worker.last_cycle_at)}</div>
    </div>
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">다음 실행 예정</div>
      <div class="worker-monitor-value">${formatDateTime(payload.worker.next_cycle_at)}</div>
      <div class="worker-monitor-note">${formatRelative(payload.worker.next_cycle_at)}</div>
    </div>
    <div class="worker-monitor-card">
      <div class="worker-monitor-label">최근 사이클 결과</div>
      <div class="worker-monitor-value">${escapeHtml(String(payload.worker.cycle_count || 0))}회 실행</div>
      <div class="worker-monitor-note">시그널 ${escapeHtml(String(lastResult.last_signal_count ?? payload.worker.last_signal_count ?? 0))}건 · 주문 ${escapeHtml(String(lastResult.last_order_count ?? payload.worker.last_order_count ?? 0))}건</div>
    </div>
  `;

  $("#system-status").innerHTML = `
    <div class="system-panel">
      <div class="system-grid">
        <div class="system-card">
          <span>실행 모드</span>
          <strong>${escapeHtml(modeText)}</strong>
        </div>
        <div class="system-card">
          <span>의존성 상태</span>
          <strong>${escapeHtml(payload.diagnostics.summary)}</strong>
        </div>
        <div class="system-card">
          <span>최근 실행 결과</span>
          <strong>${escapeHtml(payload.worker.last_summary || "아직 없음")}</strong>
        </div>
        <div class="system-card">
          <span>다음 실행 예정</span>
          <strong>${formatRelative(payload.worker.next_cycle_at)}</strong>
        </div>
        <div class="system-card">
          <span>운영 단계</span>
          <strong>${escapeHtml(policy.stage || "-")}</strong>
        </div>
        <div class="system-card">
          <span>긴급 정지</span>
          <strong>${policy.emergency_stop?.enabled ? "활성" : "해제"}</strong>
        </div>
      </div>
      <details class="details-card">
        <summary>진단 상세 JSON 보기</summary>
        <pre class="json-view">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
      </details>
    </div>
  `;
}

function renderSummaryStrip(portfolio, signals, system) {
  const recentSignals = signals.signals || [];
  const buyCandidates = recentSignals.filter((signal) => signal.buy_signal).length;
  const workerText = system.worker.running ? "실행 중" : "대기 중";
  const drawdown = portfolio.risk?.drawdown_pct || 0;

  $("#summary-strip").innerHTML = `
    <div class="summary-card">
      <div class="summary-label">오늘의 시그널</div>
      <div class="summary-value">${recentSignals.length}건</div>
      <div class="summary-note">매수 후보 ${buyCandidates}건</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">리스크 상태</div>
      <div class="summary-value ${toneClass(drawdown)}">${percent(drawdown)}</div>
      <div class="summary-note">${portfolio.risk?.sleep_mode ? "휴면 모드" : "정상 운영"}</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">에이전트 워커</div>
      <div class="summary-value">${escapeHtml(workerText)}</div>
      <div class="summary-note ${system.worker.running ? "live-note" : ""}">${system.worker.running ? `다음 실행 ${formatRelative(system.worker.next_cycle_at)}` : (system.worker.last_cycle_at ? `마지막 실행 ${formatRelative(system.worker.last_cycle_at)}` : "아직 실행 이력 없음")}</div>
    </div>
  `;
}

async function loadDashboard(isAutoRefresh = false) {
  if (refreshInFlight) return;
  refreshInFlight = true;
  setSyncState("동기화 중", isAutoRefresh ? "자동으로 최신 상태를 가져오는 중입니다." : "화면을 갱신하는 중입니다.", "warning");
  let workerRunning = false;

  try {
    const [portfolio, signals, orders, backtests, system, safety, audit] = await Promise.all([
      api("/api/portfolio"),
      api("/api/signals"),
      api("/api/orders"),
      api("/api/backtests"),
      api("/api/system/status"),
      api("/api/safety"),
      api("/api/audit"),
    ]);

    renderPortfolio(portfolio);
    renderSignals(signals);
    renderOrders(orders);
    renderBacktests(backtests);
    renderSafety(safety);
    renderAudit(audit);
    renderSystem(system, safety.policy || {});
    renderSummaryStrip(portfolio, signals, system);
    renderEquityChart(portfolio.equity || []);
    renderSignalChart(signals.signals || []);

    workerRunning = Boolean(system.worker.running);
    const nextMessage = workerRunning
      ? `자동 갱신 ${Math.round(ACTIVE_REFRESH_MS / 1000)}초 주기 · 다음 실행 ${formatRelative(system.worker.next_cycle_at)}`
      : `자동 갱신 ${Math.round(IDLE_REFRESH_MS / 1000)}초 주기 · 마지막 동기화 ${formatDateTime(new Date().toISOString())}`;
    setSyncState("동기화 완료", nextMessage, workerRunning ? "success" : "warning");
  } finally {
    refreshInFlight = false;
    scheduleRefresh(workerRunning);
  }
}

async function postJson(path, payload) {
  return api(path, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

$("#refresh-analysis").addEventListener("click", async () => {
  try {
    await postJson("/api/analysis/refresh", { session: "AUTO", force_refresh: true });
    await loadDashboard();
    toast("분석을 새로고침했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#run-cycle").addEventListener("click", async () => {
  try {
    await postJson("/api/agent/cycle", { session: "AUTO", force_refresh: false, place_orders: true });
    await loadDashboard();
    toast("에이전트 사이클을 실행했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#worker-start").addEventListener("click", async () => {
  try {
    await postJson("/api/agent/worker/start", { interval_sec: 60, session: "AUTO", place_orders: true });
    await loadDashboard();
    toast("워커를 시작했습니다. 자동으로 60초마다 분석/주문 사이클을 실행합니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#worker-stop").addEventListener("click", async () => {
  try {
    await postJson("/api/agent/worker/stop", {});
    await loadDashboard();
    toast("워커를 중지했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#emergency-stop-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const reason = String($("#stop-reason").value || "").trim();
  try {
    await postJson("/api/safety/emergency-stop", { enabled: true, reason });
    await loadDashboard();
    toast("긴급 정지를 활성화했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#clear-emergency-stop").addEventListener("click", async () => {
  try {
    await postJson("/api/safety/emergency-stop", { enabled: false, reason: "" });
    await loadDashboard();
    toast("긴급 정지를 해제했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#stage-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await postJson("/api/safety/stage", { stage: String($("#stage-select").value) });
    await loadDashboard();
    toast("운영 단계를 변경했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#run-backtest").addEventListener("click", async () => {
  try {
    await postJson("/api/backtests/run", { days: 30, initial_cash: 10000000 });
    await loadDashboard();
    toast("백테스트를 실행했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#order-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  const payload = {
    stock_code: String(formData.get("stock_code") || "").trim(),
    session: String(formData.get("session")),
    side: String(formData.get("side")),
    qty: Number(formData.get("qty")),
  };

  try {
    await postJson("/api/orders/paper", payload);
    await loadDashboard();
    toast("Paper 주문을 처리했습니다.");
  } catch (error) {
    toast(error.message, true);
  }
});

loadDashboard().catch((error) => toast(error.message, true));
window.setInterval(() => loadDashboard().catch(() => {}), 15000);

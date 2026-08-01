"""
dashboard.py - alpha-gen 글로벌 테마 자율 에이전트 웹 대시보드
실행: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import market_data
import news_analyzer
import risk_manager

# ─── 페이지 기본 설정 ───────────────────────────────────────
st.set_page_config(
    page_title="alpha-gen 에이전트 대시보드",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

KST = ZoneInfo("Asia/Seoul")

# 대상 종목 전체 통합 정의
TARGET_STOCKS = {**config.KR_STOCKS, **config.US_STOCKS}

# ══════════════════════════════════════════════════════════════
# 커스텀 CSS (다크 테마 + Glassmorphism + 프리미엄 그라데이션)
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    color: #e2e8f0;
}

/* 전체 배경 그라데이션 */
.stApp {
    background: radial-gradient(circle at 50% 50%, #0d0e15 0%, #07080c 100%);
}

/* 메트릭 카드 Glassmorphism */
[data-testid="metric-container"] {
    background: rgba(30, 41, 59, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 24px;
    backdrop-filter: blur(16px);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
[data-testid="metric-container"]:hover {
    transform: translateY(-4px);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.15);
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: rgba(10, 11, 18, 0.95);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}

/* 섹션 헤더 */
.section-header {
    font-size: 1.25rem;
    font-weight: 700;
    color: #a5b4fc;
    margin: 32px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid rgba(165, 180, 252, 0.15);
    letter-spacing: 0.5px;
}

/* 배지 스타일 */
.badge {
    padding: 6px 14px;
    border-radius: 30px;
    font-size: 0.8rem;
    font-weight: 700;
    display: inline-block;
    letter-spacing: 0.5px;
}
.badge-mock {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: #07080c;
    box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
}
.badge-live {
    background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
    color: #ffffff;
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
    animation: pulse 2s infinite;
}
.badge-real {
    background: linear-gradient(135deg, #10b981 0%, #047857 100%);
    color: #07080c;
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(0.98); }
}

/* 알림 상자 */
.info-box {
    background: rgba(99, 102, 241, 0.08);
    border-left: 4px solid #6366f1;
    border-radius: 12px;
    padding: 16px 20px;
    margin: 16px 0;
    font-size: 0.9rem;
    color: #c7d2fe;
}

/* 태그 클라우드 */
.tag-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 0;
}
.keyword-tag {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.2s ease;
}
.keyword-tag:hover {
    background: rgba(99, 102, 241, 0.3);
    transform: scale(1.05);
    border-color: #818cf8;
}

/* 리스크 바 */
.risk-bar-container {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    height: 16px;
    width: 100%;
    margin-top: 8px;
    overflow: hidden;
}
.risk-bar-fill {
    background: linear-gradient(90deg, #6366f1 0%, #ec4899 100%);
    height: 100%;
    border-radius: 8px;
    transition: width 0.5s ease-in-out;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# [1] 데이터 로드 (Mock 또는 Real API 분기)
# ══════════════════════════════════════════════════════════════

def fetch_real_balance():
    """실제 KIS API 잔고 연동 및 대시보드 포맷 변환"""
    try:
        cash, holdings = market_data.get_balance("KR")
        formatted = []
        for h in holdings:
            avg_p = h["avg_price"]
            cur_p = h["eval_price"]
            pnl_rate = (cur_p - avg_p) / avg_p * 100 if avg_p else 0.0
            formatted.append({
                "종목명": h["name"],
                "코드": h["code"],
                "수량(주)": h["qty"],
                "평균단가(원)": avg_p,
                "현재가(원)": cur_p,
                "평가금액(원)": cur_p * h["qty"],
                "수익률(%)": round(pnl_rate, 2),
                "목표가(원)": "-",
                "상태": "✅ 보유중",
            })
        return cash, formatted, None
    except Exception as e:
        return 0, [], str(e)


# ── 에이전트 상태 로드 (Mock/실전 공통: 감성·휴면·bought_today)
market_data.load_agent_state()


def build_equity_plotly_chart(df_equity: pd.DataFrame, init_cap: int, dd_limit_pct: float) -> go.Figure:
    """총자산 추이 + 초기 원금 기준선 + 드로우다운 오버레이"""
    df = df_equity.sort_values("time").copy()
    df["peak"] = df["total"].cummax()
    df["drawdown_pct"] = (df["total"] - df["peak"]) / df["peak"] * 100

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["total"],
            name="총자산",
            mode="lines",
            line=dict(color="#818cf8", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(99, 102, 241, 0.12)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=[init_cap] * len(df),
            name="초기 원금",
            mode="lines",
            line=dict(color="#f59e0b", width=1.5, dash="dash"),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["drawdown_pct"],
            name="드로우다운 (%)",
            mode="lines",
            line=dict(color="#f43f5e", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(244, 63, 94, 0.18)",
        ),
        secondary_y=True,
    )
    fig.add_hline(
        y=-dd_limit_pct,
        line_dash="dot",
        line_color="#ef4444",
        line_width=1,
        secondary_y=True,
        annotation_text=f"휴면 한계 -{dd_limit_pct:.0f}%",
        annotation_position="bottom right",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=360,
        margin=dict(l=40, r=40, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(title_text="총자산 (원)", secondary_y=False, showgrid=True, gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(title_text="드로우다운 (%)", secondary_y=True, showgrid=False)
    return fig


# ── 데이터 로드 실행
if config.MOCK_MODE:
    cash, holdings_data = market_data.mock_get_balance()
    trade_logs = market_data.mock_trade_log
    api_error = None
    
    # 대시보드용 테이블 데이터 포맷팅
    formatted_holdings = []
    for h in holdings_data:
        code = h["code"]
        avg_p = h["avg_price"]
        cur_p = h["eval_price"]
        pnl_rate = (cur_p - avg_p) / avg_p * 100 if avg_p else 0.0
        
        # 임의의 목표가 표시 (RSI 등 기술지표 기준)
        history = market_data._mock_prices.get(code, avg_p)
        formatted_holdings.append({
            "종목명": h["name"],
            "코드": code,
            "수량(주)": h["qty"],
            "평균단가(원)": avg_p,
            "현재가(원)": cur_p,
            "평가금액(원)": cur_p * h["qty"],
            "수익률(%)": round(pnl_rate, 2),
            "목표가(원)": int(cur_p * 1.03), # 대략적인 시각용
            "상태": "✅ 매수완료",
        })
    holdings_display = formatted_holdings
else:
    cash, holdings_display, api_error = fetch_real_balance()
    trade_logs = list(market_data.mock_trade_log)

# 전체 자산 합산
total_eval = sum(h["평가금액(원)"] for h in holdings_display)
total_buy  = sum(h["평균단가(원)"] * h["수량(주)"] for h in holdings_display)
total_asset = cash + total_eval
total_pnl   = total_eval - total_buy
pnl_rate    = (total_pnl / total_buy * 100) if total_buy else 0.0


# ══════════════════════════════════════════════════════════════
# [2] 사이드바 구현
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🤖 alpha-gen 설정")
    st.markdown("---")

    # 모드 및 상태 배지
    mode_text = "MOCK 시뮬레이션" if config.MOCK_MODE else ("실전투자 🔴" if config.IS_REAL_TRADING else "모의투자 🟡")
    badge_class = "badge-mock" if config.MOCK_MODE else ("badge-live" if config.IS_REAL_TRADING else "badge-real")
    st.markdown(f'<span class="badge {badge_class}">{mode_text}</span>', unsafe_allow_html=True)
    st.markdown("")

    # 세션 헬퍼 정보
    st.markdown("**⏰ 활성 거래 세션**")
    st.markdown(f"- **국장 (KR)**: `{config.KR_BUY_START}` ~ `{config.KR_SELL_TIME}`")
    st.markdown(f"- **미장 (US)**: `{config.US_MARKET_OPEN}` ~ `{config.US_MARKET_CLOSE}` (KST)")
    st.markdown(f"- **RSI 과매수 기준**: `{config.RSI_OVERBOUGHT}`")
    st.markdown(f"- **리스크 한도**: 종목당 `{config.MAX_POSITION_PCT*100:.0f}%` / 손절 `-{config.STOP_LOSS_PCT*100:.0f}%` / 드로우다운 `-{config.MAX_DRAWDOWN_PCT*100:.0f}%` ")

    st.markdown("---")
    st.markdown("**📌 모니터링 종목**")
    for code, info in config.KR_STOCKS.items():
        st.markdown(f"- 🇰🇷 `{code}` **{info['name']}**")
    for code, info in config.US_STOCKS.items():
        st.markdown(f"- 🇺🇸 `{code}` **{info['name']}**")

    st.markdown("---")
    auto_refresh = st.toggle("🔄 실시간 동기화 (5초)", value=True)
    if st.button("🔃 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="info-box">💡 <b>에이전트 제어</b><br>터미널에서 <code>main.py</code>를 실행해두면 실시간 가격 틱과 거래가 본 대시보드에 즉시 반영됩니다.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# [3] 메인 헤더 & 시장 세션 상태
# ══════════════════════════════════════════════════════════════
col_title, col_session = st.columns([3, 1])

with col_title:
    st.markdown("# 📈 alpha-gen 자율 매매 에이전트")
    st.markdown("뉴스 감성(Claude) + 기술적 분석 + 듀얼 마켓 모니터링 대시보드")

# 시장 세션 판별
session = market_data.get_market_session()
session_labels = {
    "KR": "🇰🇷 한국 주식 시장 진행 중",
    "US": "🇺🇸 미국 주식 시장 진행 중",
    "CLOSED": "⏸️ 장외 휴식 시간"
}
session_color = {
    "KR": "#3b82f6",
    "US": "#ec4899",
    "CLOSED": "#64748b"
}

with col_session:
    st.markdown(f"<br><div style='text-align:right;'><span style='background-color:{session_color[session]}; color:#000000; font-weight:700; padding:8px 16px; border-radius:30px; font-size:0.9rem;'>{session_labels[session]}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:right; color:#64748b; font-size:0.8rem; margin-top:8px;'>마지막 동기화: {datetime.now(KST).strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════
# [4] 자산 현황 요약 (섹션 1)
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">💰 자산 및 포트폴리오 요약</div>', unsafe_allow_html=True)

if api_error:
    st.error(f"⚠️ KIS API 연동 에러: {api_error}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 예수금 (Cash)", f"{cash:,} 원")
c2.metric("📦 주식 평가금액", f"{total_eval:,} 원")
c3.metric("🏦 총 평가자산", f"{total_asset:,} 원")
c4.metric(
    "📊 총 평가손익",
    f"{total_pnl:+,} 원",
    delta=f"{pnl_rate:+.2f}%",
    delta_color="normal"
)

# ── 총자산 추이 꺾은선 그래프
st.markdown('<div class="section-header">📈 총자산 추이 (Equity Curve)</div>', unsafe_allow_html=True)
equity_rows = list(getattr(market_data, "equity_history", []))
if not equity_rows and total_asset:
    equity_rows = [{"time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), "total": total_asset}]

if equity_rows:
    df_equity = pd.DataFrame(equity_rows)
    df_equity["time"] = pd.to_datetime(df_equity["time"])
    df_equity = df_equity.sort_values("time")
    init_cap = risk_manager.INITIAL_CAPITAL or config.MOCK_INITIAL_CASH
    dd_limit = config.MAX_DRAWDOWN_PCT * 100
    fig_equity = build_equity_plotly_chart(df_equity, init_cap, dd_limit)
    st.plotly_chart(fig_equity, use_container_width=True)
    if len(df_equity) >= 2:
        first, last = int(df_equity["total"].iloc[0]), int(df_equity["total"].iloc[-1])
        chg = last - first
        chg_pct = chg / first * 100 if first else 0
        peak = int(df_equity["total"].cummax().iloc[-1])
        cur_dd = (last - peak) / peak * 100 if peak else 0
        st.caption(
            f"기록 {len(df_equity)}개 · 시작 {first:,}원 → 현재 {last:,}원 "
            f"({chg:+,}원 / {chg_pct:+.2f}%) · 기준 원금 {init_cap:,}원 · "
            f"현재 드로우다운 {cur_dd:.2f}%"
        )
    if config.MOCK_MODE:
        continuous = getattr(config, "MOCK_CONTINUOUS", False)
        mode_hint = "연속 루프" if continuous else "장외 1회 종료"
        st.caption(f"💡 `main.py` 실행 중 루프마다 갱신됩니다 (Mock {mode_hint}). 대시보드 5초 새로고침과 함께 확인하세요.")
else:
    st.info("아직 자산 추이 데이터가 없습니다. `python main.py`를 실행하면 그래프가 쌓입니다.")


# ══════════════════════════════════════════════════════════════
# [5] 리스크 분석 게이지 & 휴면 상태 (섹션 2)
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">🛡️ 실시간 리스크 제어 현황</div>', unsafe_allow_html=True)

risk_col, sleep_col = st.columns([2, 1])

# 드로우다운 계산
dd_pct = risk_manager.get_drawdown_pct(total_asset)
dd_limit = config.MAX_DRAWDOWN_PCT * 100
dd_progress = min(1.0, max(0.0, abs(dd_pct) / dd_limit))

with risk_col:
    st.markdown(f"**📉 누적 드로우다운 (Drawdown) 현황** : `{dd_pct:.2f}%` / 한계치 `-{dd_limit:.0f}%`")
    # 리스크 게이지 바
    st.markdown(f"""
    <div class="risk-bar-container">
        <div class="risk-bar-fill" style="width: {dd_progress*100:.1f}%;"></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#64748b; margin-top:4px;'>*누적 드로우다운이 -{dd_limit:.0f}%에 도달하면 에이전트가 모든 포지션을 긴급 청산하고 '휴면 모드'로 자동 전환됩니다.</div>", unsafe_allow_html=True)

with sleep_col:
    # 휴면 모드 상태 표시 — main.py 실시간 루프가 기준으로 삼는 alpha_gen.sqlite3에서 직접 조회
    # (agent_state.db는 크래시 종료 시에만 갱신되는 백업이라 여기서 참조하면 상태가 어긋날 수 있음, spec.md P1 참고)
    is_sleep, sleep_reason_text = market_data.get_live_sleep_state()
    if is_sleep:
        st.markdown(f"""
        <div style='background-color:rgba(239,68,68,0.15); border:1px solid #ef4444; border-radius:12px; padding:12px 18px;'>
            <span style='color:#ef4444; font-weight:700; font-size:1.1rem;'>🛑 에이전트 휴면 모드 가동 중</span><br>
            <span style='color:#fca5a5; font-size:0.85rem;'>사유: {sleep_reason_text}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background-color:rgba(16,185,129,0.1); border:1px solid #10b981; border-radius:12px; padding:12px 18px; text-align:center;'>
            <span style='color:#10b981; font-weight:700; font-size:1.1rem;'>🟢 에이전트 정상 가동 중</span><br>
            <span style='color:#a7f3d0; font-size:0.85rem;'>실시간 뉴스 및 차트 감시 중</span>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# [6] 감성 점수 막대 차트 & 키워드 태그 클라우드 (섹션 3)
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">🤖 뉴스 감성 및 AI 키워드 분석</div>', unsafe_allow_html=True)

col_chart, col_keywords = st.columns([1, 1])

# 감성 데이터 구성
sentiments = []
keywords_pool = []

sentiment_source = market_data._shared_sentiments or {}
for code, info in TARGET_STOCKS.items():
    sent_data = news_analyzer.get_stock_sentiment(code, sentiment_source)
    sentiments.append({
        "종목명": info["name"],
        "코드": code,
        "감성점수": sent_data["score"],
        "감성등급": sent_data["label"],
        "이유": sent_data["reason"]
    })
    keywords_pool.extend(sent_data.get("keywords", []))

df_sent = pd.DataFrame(sentiments)

with col_chart:
    st.markdown("**📊 종목별 실시간 감성 점수 (-2 ~ +2)**")
    # 가로 막대 차트 렌더링
    st.bar_chart(df_sent.set_index("종목명")["감성점수"], height=220)

with col_keywords:
    st.markdown("**🏷️ 실시간 핵심 수집 키워드 (Word Tag Cloud)**")
    unique_keywords = list(set(keywords_pool))
    if not unique_keywords:
        # Mock 고정 데이터 추가
        unique_keywords = ["FSD v13", "Blackwell", "HBM4", "EV Margins", "NASA", "SpaceX Starship", "Operating Profit", "Defense AI"]
    
    st.markdown('<div class="tag-container">', unsafe_allow_html=True)
    tags_html = "".join([f'<span class="keyword-tag">{kw}</span>' for kw in unique_keywords])
    st.markdown(tags_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 최신 뉴스 요약 표시
    st.markdown("**📰 AI 판단 근거 요약**")
    for idx, row in df_sent.iterrows():
        if row["감성점수"] != 0:
            color = "#818cf8" if row["감성점수"] > 0 else "#fca5a5"
            st.markdown(f"- <span style='color:{color}; font-weight:600;'>{row['종목명']}</span> : {row['이유']}", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# [7] 보유 종목 테이블 & 매매 이력 (섹션 4)
# ══════════════════════════════════════════════════════════════
col_tbl, col_log = st.columns([5, 3])

with col_tbl:
    st.markdown('<div class="section-header">📦 현재 보유 및 감시 종목</div>', unsafe_allow_html=True)
    if holdings_display:
        df_hold = pd.DataFrame(holdings_display)
        
        # 수익률 포맷 색상화
        def color_pnl(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #10b981; font-weight: 700;"
                elif val < 0:
                    return "color: #f43f5e; font-weight: 700;"
            return ""

        show_cols = ["종목명", "코드", "수량(주)", "평균단가(원)", "현재가(원)", "평가금액(원)", "수익률(%)", "목표가(원)", "상태"]
        df_display = df_hold[show_cols].copy()
        
        # 숫자 콤마 적용
        for col in ["평균단가(원)", "현재가(원)", "평가금액(원)", "목표가(원)"]:
            df_display[col] = df_display[col].apply(lambda x: f"{x:,}" if isinstance(x, int) else x)

        st.dataframe(
            df_display.style.applymap(color_pnl, subset=["수익률(%)"]),
            use_container_width=True,
            height=200,
            hide_index=True
        )
    else:
        st.info("현재 포트폴리오에 보유 중인 종목이 없습니다. 에이전트가 매수 조건을 감시 중입니다.")

with col_log:
    st.markdown('<div class="section-header">📋 에이전트 매매 이력</div>', unsafe_allow_html=True)
    if trade_logs:
        df_logs = pd.DataFrame(trade_logs)
        
        # 컬럼 이름 맞춤
        log_cols = {
            "time": "시각", "action": "구분", "name": "종목명", 
            "qty": "수량(주)", "price": "단가(원)", "amount": "금액(원)", "pnl": "실현손익(원)"
        }
        df_logs_show = df_logs.rename(columns=log_cols)
        
        # 숫자 포맷 적용
        for col in ["단가(원)", "금액(원)", "실현손익(원)"]:
            if col in df_logs_show.columns:
                df_logs_show[col] = df_logs_show[col].apply(lambda x: f"{x:,}" if isinstance(x, (int, float)) else "-")
        
        st.dataframe(
            df_logs_show[["시각", "구분", "종목명", "수량(주)", "단가(원)", "실현손익(원)"]],
            use_container_width=True,
            height=200,
            hide_index=True
        )
    else:
        st.info("아직 매매 이력이 존재하지 않습니다.")


# ══════════════════════════════════════════════════════════════
# [8] 종목별 시세 동향 (섹션 5)
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📉 실시간 가격 동향 (미장/국장 모니터링)</div>', unsafe_allow_html=True)

# 활성 세션 종목 위주로 차트 렌더링
active_stocks = config.KR_STOCKS if session == "KR" else config.US_STOCKS if session == "US" else TARGET_STOCKS
cols_charts = st.columns(len(active_stocks))

# 복잡하지 않게 오늘 가격 변동 차트 생성
for idx, (code, info) in enumerate(active_stocks.items()):
    with cols_charts[idx]:
        st.markdown(f"**{info['name']} ({code})**")
        
        # 시뮬레이션용 가격 데이터 생성
        prices_list = []
        base = config.MOCK_SEED_PRICES.get(code, 50000)
        curr = market_data._mock_prices.get(code, base)
        
        # 30분 전부터 현재까지 가격 추이 시뮬
        random.seed(hash(code))
        pt = curr * 0.98
        for i in range(20):
            pt = pt * random.uniform(0.995, 1.006)
            prices_list.append(pt)
        prices_list.append(curr)
        
        df_chart = pd.DataFrame({"가격(원)": prices_list})
        st.line_chart(df_chart, height=180)
        
        chg_pct = (curr - base) / base * 100
        sign = "🟢" if chg_pct >= 0 else "🔴"
        st.markdown(f"{sign} 현재가: `{int(curr):,}원` ({chg_pct:+.2f}%)")


# ══════════════════════════════════════════════════════════════
# 자동 새로고침 처리
# ══════════════════════════════════════════════════════════════
if auto_refresh:
    import time
    time.sleep(5)
    st.rerun()

"""
market_data.py — 시장 데이터 통합 모듈

[세션 분기]
  KR 세션 (09:00~15:30 KST): 한국투자증권 KIS API
  US 세션 (22:30~05:00 KST): yfinance (실시간 미장 시세)
  Mock 모드: 랜덤워크 가격 생성

[지원 기능]
  - 현재 세션 판별
  - 현재가 / 전일 데이터 조회
  - 잔고 조회
  - Mock 포트폴리오 상태 관리
"""

import random
import math
import time
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo
import config
from state_store import StateStore

_store = StateStore(config.DATA_DIR / "agent_state.db")

KST = ZoneInfo("Asia/Seoul")

# ──────────────────────────────────────────────
# KIS API 토큰 캐시
# ──────────────────────────────────────────────
_kis_token: str = ""
_kis_token_expires: Optional[datetime] = None
_kis_token_blocked_until: Optional[datetime] = None
_kis_api_degraded_until: Optional[datetime] = None
_kis_token_lock = threading.Lock()
_kis_request_lock = threading.Lock()
_kis_last_request_at: Optional[datetime] = None
_KIS_TOKEN_CACHE_FILE = config.DATA_DIR / "kis_token_cache.json"

# ──────────────────────────────────────────────
# Mock 포트폴리오 상태 (메모리)
# ──────────────────────────────────────────────
_mock_cash: int = config.MOCK_INITIAL_CASH
_mock_holdings: dict[str, dict] = {}
_mock_prices: dict[str, float] = {
    code: float(price) for code, price in config.MOCK_SEED_PRICES.items()
}
mock_trade_log: list[dict] = []   # 대시보드 공유

# ──────────────────────────────────────────────
# 에이전트 공유 상태 (파일 영속화)
# ──────────────────────────────────────────────
_shared_sentiments: dict = {}
agent_bought_today: set[str] = set()
agent_bought_today_date: str = ""
agent_last_news_fetch: Optional[str] = None  # ISO 형식
equity_history: list[dict] = []  # {"time", "total", "cash", "session"}
MAX_EQUITY_HISTORY = 2000


# ══════════════════════════════════════════════
# [1] 세션 판별
# ══════════════════════════════════════════════

def get_market_session() -> str:
    """
    현재 시각 기준 활성 시장 세션 반환.
    Returns: "KR" | "US" | "CLOSED"
    """
    now = datetime.now(KST)
    t = now.strftime("%H:%M")

    # 한국장: 09:00 ~ 15:30
    if config.KR_MARKET_OPEN <= t <= config.KR_MARKET_CLOSE:
        return "KR"

    # 미국장: 22:30 ~ 05:00 (KST, 자정 걸침)
    if t >= config.US_MARKET_OPEN or t <= config.US_MARKET_CLOSE:
        return "US"

    return "CLOSED"


def get_target_stocks_for_session(session: str) -> dict:
    """세션에 맞는 종목 딕셔너리 반환"""
    if session == "KR":
        return config.KR_STOCKS
    elif session == "US":
        return config.US_STOCKS
    elif session == "BOTH":
        return {**config.KR_STOCKS, **config.US_STOCKS}
    return {}


# ══════════════════════════════════════════════
# [2] Mock 시세 엔진
# ══════════════════════════════════════════════

def _tick_mock_prices() -> None:
    """Mock 현재가 업데이트 (랜덤워크 ±0.5%)"""
    for code in _mock_prices:
        change = random.uniform(-0.005, 0.005)
        _mock_prices[code] = max(100.0, _mock_prices[code] * (1 + change))


def mock_get_price(stock_code: str) -> dict:
    _tick_mock_prices()
    cur = _mock_prices.get(stock_code, 50_000.0)
    base = config.MOCK_SEED_PRICES.get(stock_code, int(cur))
    return {
        "current_price": int(cur),
        "open_price":    int(base * random.uniform(0.99, 1.01)),
        "high_price":    int(cur * 1.01),
        "low_price":     int(cur * 0.99),
    }


def mock_get_prev_day(stock_code: str) -> dict:
    base = config.MOCK_SEED_PRICES.get(stock_code, 50_000)
    prev_close = int(base * random.uniform(0.97, 1.03))
    return {
        "prev_high":  int(prev_close * random.uniform(1.01, 1.025)),
        "prev_low":   int(prev_close * random.uniform(0.975, 0.99)),
        "prev_close": prev_close,
    }


def mock_get_balance() -> tuple[int, list[dict]]:
    for code, h in _mock_holdings.items():
        h["eval_price"] = int(_mock_prices.get(code, h["avg_price"]))
    holdings = list(_mock_holdings.values())
    return _mock_cash, holdings


# MOCK_STATE_FILE = "mock_state.json"  # 레거시 — agent_state.db 전환 후 미사용


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def record_equity_snapshot(total_asset: int, session: str = "", cash: Optional[int] = None) -> None:
    """총자산 스냅샷 기록 (대시보드 꺾은선 그래프용)"""
    global equity_history
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    if equity_history and equity_history[-1].get("time") == now_str:
        return
    equity_history.append({
        "time": now_str,
        "total": int(total_asset),
        "cash": cash,
        "session": session,
    })
    if len(equity_history) > MAX_EQUITY_HISTORY:
        equity_history = equity_history[-MAX_EQUITY_HISTORY:]
    _store.append_equity(now_str, int(total_asset), cash, session)


def ensure_bought_today_date() -> None:
    """날짜가 바뀌면 bought_today 초기화"""
    global agent_bought_today, agent_bought_today_date
    today = _today_kst()
    if agent_bought_today_date and agent_bought_today_date != today:
        agent_bought_today = set()
    agent_bought_today_date = today


def clear_bought_today() -> None:
    global agent_bought_today
    agent_bought_today = set()
    ensure_bought_today_date()
    _store.clear_bought_today()


def add_bought_today(code: str) -> None:
    ensure_bought_today_date()
    agent_bought_today.add(code)
    _store.add_bought_today(code)


def remove_bought_today(code: str) -> None:
    agent_bought_today.discard(code)
    _store.remove_bought_today(code)


def is_bought_today(code: str) -> bool:
    ensure_bought_today_date()
    return code in agent_bought_today  # in-memory set은 add/remove/clear로 _store와 동기화됨


def _apply_agent_fields(state: dict) -> None:
    """JSON에서 에이전트 공통 필드 복원"""
    global _shared_sentiments, agent_bought_today, agent_bought_today_date
    global agent_last_news_fetch, equity_history

    import risk_manager

    _shared_sentiments = state.get("sentiments", state.get("_shared_sentiments", {}))
    saved_date = state.get("bought_today_date", "")
    today = _today_kst()
    if saved_date == today:
        agent_bought_today = set(state.get("bought_today", []))
        agent_bought_today_date = today
    else:
        agent_bought_today = set()
        agent_bought_today_date = today

    agent_last_news_fetch = state.get("last_news_fetch")
    equity_history = list(state.get("equity_history", []))

    # Mock: 테스트용 휴면 상태가 파일에 남아 루프가 막히는 것 방지
    if config.MOCK_MODE:
        risk_manager.SLEEP_MODE = False
        risk_manager.SLEEP_REASON = ""
    else:
        risk_manager.SLEEP_MODE = bool(state.get("sleep_mode", False))
        risk_manager.SLEEP_REASON = state.get("sleep_reason", "")

    initial = state.get("initial_capital")
    if initial is not None:
        risk_manager.set_initial_capital(int(initial))


def _build_state_dict() -> dict:
    """저장용 통합 상태 스냅샷"""
    import risk_manager

    ensure_bought_today_date()
    state = {
        "last_updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "bought_today": sorted(agent_bought_today),
        "bought_today_date": agent_bought_today_date or _today_kst(),
        "sleep_mode": risk_manager.SLEEP_MODE,
        "sleep_reason": risk_manager.SLEEP_REASON,
        "sentiments": _shared_sentiments,
        "last_news_fetch": agent_last_news_fetch,
        "initial_capital": risk_manager.INITIAL_CAPITAL,
        "equity_history": equity_history,
    }
    if config.MOCK_MODE:
        state.update({
            "cash": _mock_cash,
            "holdings": _mock_holdings,
            "prices": _mock_prices,
            "trade_log": mock_trade_log,
        })
    return state


def save_agent_state() -> None:
    """에이전트 상태를 agent_state.db에 저장 (Mock/실전 공통)"""
    try:
        _store.save(_build_state_dict())
    except Exception as e:
        print(f"[WARN] 에이전트 상태 저장 실패: {e}")


def save_mock_state() -> None:
    """하위 호환 별칭"""
    save_agent_state()


def load_agent_state() -> None:
    """agent_state.db에서 에이전트 + Mock 포트폴리오 로드"""
    global _mock_cash, _mock_holdings, _mock_prices, mock_trade_log
    try:
        state = _store.load()
        _apply_agent_fields(state)
        if config.MOCK_MODE:
            _mock_cash = state.get("cash", _mock_cash)
            _mock_holdings = state.get("holdings", _mock_holdings)
            raw_prices = state.get("prices", {})
            if raw_prices:
                _mock_prices.update({k: float(v) for k, v in raw_prices.items()})
            mock_trade_log.clear()
            mock_trade_log.extend(state.get("trade_log", []))
    except Exception as e:
        print(f"[WARN] 에이전트 상태 로드 실패: {e}")
        ensure_bought_today_date()


def load_mock_state() -> None:
    """하위 호환 별칭"""
    load_agent_state()


def set_last_news_fetch(dt: datetime) -> None:
    global agent_last_news_fetch
    agent_last_news_fetch = dt.isoformat()


def get_last_news_fetch() -> Optional[datetime]:
    if not agent_last_news_fetch:
        return None
    try:
        return datetime.fromisoformat(agent_last_news_fetch).replace(tzinfo=KST)
    except ValueError:
        return None


def get_mock_total_asset() -> int:
    cash, holdings = mock_get_balance()
    return cash + sum(h["eval_price"] * h["qty"] for h in holdings)


# ══════════════════════════════════════════════
# [3] KIS API (한국장)
# ══════════════════════════════════════════════

def reset_kis_token_cache() -> None:
    global _kis_token, _kis_token_expires
    _kis_token = ""
    _kis_token_expires = None


def get_kis_token_meta() -> dict[str, Any]:
    """KIS OAuth 토큰 캐시 메타 (만료 시각 등)."""
    expires_at = _kis_token_expires.isoformat() if _kis_token_expires else None
    return {
        "cached": bool(_kis_token),
        "expires_at": expires_at,
        "auth_blocked_reason": kis_auth_blocked_reason(),
        "api_degraded_reason": kis_api_degraded_reason(),
    }


def kis_auth_blocked_reason() -> str | None:
    now = datetime.now(KST)
    if _kis_token_blocked_until and now < _kis_token_blocked_until:
        remaining = int((_kis_token_blocked_until - now).total_seconds())
        return (
            f"KIS OAuth cooldown ({remaining}s left): "
            "모의 APP_KEY/SECRET 확인 또는 호출 제한 해제 대기"
        )
    return None


def kis_api_degraded_reason() -> str | None:
    now = datetime.now(KST)
    if _kis_api_degraded_until and now < _kis_api_degraded_until:
        remaining = int((_kis_api_degraded_until - now).total_seconds())
        return f"KIS API degraded mode ({remaining}s left): 서버 오류·호출 과다로 일시 중단"
    return None


def _mark_kis_api_degraded() -> None:
    global _kis_api_degraded_until
    _kis_api_degraded_until = datetime.now(KST) + timedelta(seconds=config.KIS_API_DEGRADED_COOLDOWN_SEC)


def _kis_throttle_wait() -> None:
    global _kis_last_request_at
    min_interval = max(config.KIS_API_MIN_INTERVAL_MS, 0) / 1000.0
    if min_interval <= 0:
        return
    now = datetime.now(KST)
    if _kis_last_request_at is not None:
        elapsed = (now - _kis_last_request_at).total_seconds()
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    _kis_last_request_at = datetime.now(KST)


def _kis_request_get(tr_id: str, url: str, params: dict) -> dict:
    import requests

    degraded = kis_api_degraded_reason()
    if degraded:
        raise RuntimeError(degraded)

    last_error: Exception | None = None
    retries = max(config.KIS_API_RETRY_COUNT, 1)
    for attempt in range(retries):
        try:
            with _kis_request_lock:
                _kis_throttle_wait()
                res = requests.get(url, headers=_kis_headers(tr_id), params=params, timeout=10)
            return _kis_parse_response(res)
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else 0
            if status in {401, 403} and attempt == 0:
                reset_kis_token_cache()
                continue
            if status >= 500 and attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            if status >= 500:
                _mark_kis_api_degraded()
            raise
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise last_error or RuntimeError("KIS request failed")


def _load_cached_kis_token(now: datetime) -> str | None:
    if not _KIS_TOKEN_CACHE_FILE.exists():
        return None
    try:
        payload = json.loads(_KIS_TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("app_key") != config.KIS_APP_KEY:
        return None
    if payload.get("is_real_trading") != config.IS_REAL_TRADING:
        return None
    token = str(payload.get("access_token") or "")
    expires_raw = payload.get("expires_at")
    if not token or not expires_raw:
        return None
    expires_at = datetime.fromisoformat(str(expires_raw))
    if now >= expires_at:
        return None
    return token


def _save_cached_kis_token(token: str, expires_at: datetime) -> None:
    _KIS_TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token,
        "expires_at": expires_at.isoformat(),
        "app_key": config.KIS_APP_KEY,
        "is_real_trading": config.IS_REAL_TRADING,
    }
    _KIS_TOKEN_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _get_kis_token(force_refresh: bool = False) -> str:
    global _kis_token, _kis_token_expires, _kis_token_blocked_until
    import requests

    now = datetime.now(KST)
    blocked = kis_auth_blocked_reason()
    if blocked:
        raise RuntimeError(blocked)

    with _kis_token_lock:
        blocked = kis_auth_blocked_reason()
        if blocked:
            raise RuntimeError(blocked)

        if not force_refresh and _kis_token and _kis_token_expires and now < _kis_token_expires:
            return _kis_token

        if not force_refresh:
            cached = _load_cached_kis_token(now)
            if cached:
                _kis_token = cached
                _kis_token_expires = now + timedelta(hours=23)
                return _kis_token

        url = f"{config.KIS_URL}/oauth2/tokenP"
        res = requests.post(
            url,
            json={
                "grant_type": "client_credentials",
                "appkey": config.KIS_APP_KEY,
                "appsecret": config.KIS_APP_SECRET,
            },
            timeout=10,
        )
        if res.status_code == 403:
            _kis_token_blocked_until = now + timedelta(seconds=config.KIS_TOKEN_COOLDOWN_SEC)
            reset_kis_token_cache()
            detail = res.text[:160].replace("\n", " ")
            raise RuntimeError(
                "KIS OAuth 403 (tokenP): 모의 APP_KEY/SECRET·계좌 확인, "
                f"또는 {config.KIS_TOKEN_COOLDOWN_SEC}초 후 재시도 (호출 제한). "
                f"detail={detail}"
            )
        res.raise_for_status()
        _kis_token = res.json()["access_token"]
        _kis_token_expires = now + timedelta(hours=23)
        _kis_token_blocked_until = None
        _save_cached_kis_token(_kis_token, _kis_token_expires)
        return _kis_token


def _kis_headers(tr_id: str) -> dict:
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "authorization": f"Bearer {_get_kis_token()}",
        "appkey": config.KIS_APP_KEY,
        "appsecret": config.KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


def _kis_parse_response(res) -> dict:
    import requests

    try:
        data = res.json()
    except ValueError as exc:
        res.raise_for_status()
        raise RuntimeError(f"KIS non-JSON response (HTTP {res.status_code})") from exc

    rt_cd = str(data.get("rt_cd", ""))
    if rt_cd not in ("", "0"):
        msg1 = data.get("msg1") or data.get("msg_cd") or "unknown KIS error"
        raise RuntimeError(f"KIS rt_cd={rt_cd} {msg1}")

    if res.status_code >= 400:
        msg1 = data.get("msg1") or res.reason or "HTTP error"
        raise requests.HTTPError(
            f"{res.status_code} Server Error: {msg1} for url: {res.url}",
            response=res,
        )
    return data


def kis_get_balance() -> tuple[int, list[dict]]:
    import time

    tr_id = "TTTC8434R" if config.IS_REAL_TRADING else "VTTC8434R"
    url = f"{config.KIS_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    param_sets = (
        {
            "CANO": config.ACCOUNT_NO,
            "ACNT_PRDT_CD": config.ACCOUNT_CODE,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        },
        {
            "CANO": config.ACCOUNT_NO,
            "ACNT_PRDT_CD": config.ACCOUNT_CODE,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "01",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        },
    )

    last_error: Exception | None = None
    for attempt, params in enumerate(param_sets):
        try:
            data = _kis_request_get(tr_id, url, params)
            output2 = data.get("output2") or []
            if not output2:
                raise RuntimeError("KIS balance response missing output2")
            cash = int(output2[0].get("dnca_tot_amt", 0))
            holdings = [
                {
                    "code": h["pdno"],
                    "name": h["prdt_name"],
                    "qty": int(h["hldg_qty"]),
                    "avg_price": int(str(h["pchs_avg_pric"]).split(".")[0] or 0),
                    "eval_price": int(h["prpr"]),
                }
                for h in data.get("output1", []) if int(h.get("hldg_qty", 0)) > 0
            ]
            return cash, holdings
        except Exception as exc:
            last_error = exc
            if attempt + 1 < len(param_sets):
                time.sleep(0.3)
                continue
            raise last_error
    raise RuntimeError("KIS balance inquiry failed")


def kis_get_price(stock_code: str) -> dict:
    url = f"{config.KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
    data = _kis_request_get("FHKST01010100", url, params)
    o = data["output"]
    return {
        "current_price": int(o["stck_prpr"]),
        "open_price":    int(o["stck_oprc"]),
        "high_price":    int(o["stck_hgpr"]),
        "low_price":     int(o["stck_lwpr"]),
    }


def kis_get_price_history(stock_code: str, days: int = 30) -> list[float]:
    """KIS 일별 종가 히스토리 (과거→현재 순, RSI/MA용)"""
    url = f"{config.KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    data = _kis_request_get("FHKST01010400", url, params)
    rows = data.get("output", [])
    closes: list[float] = []
    for row in rows:
        raw = row.get("stck_clpr")
        if raw is not None and str(raw).strip() not in ("", "0"):
            closes.append(float(raw))
    closes.reverse()
    if len(closes) > days:
        closes = closes[-days:]
    return closes


def kis_get_prev_day(stock_code: str) -> dict:
    url = f"{config.KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0",
    }
    data = _kis_request_get("FHKST01010400", url, params)
    rows = data.get("output") or []
    if len(rows) < 2:
        raise ValueError(f"KIS daily price insufficient rows for {stock_code}")
    prev = rows[1]
    return {
        "prev_high":  int(prev["stck_hgpr"]),
        "prev_low":   int(prev["stck_lwpr"]),
        "prev_close": int(prev["stck_clpr"]),
    }


# KIS API 주문 관련 함수들은 order_engine.py로 분리되었습니다.


# ══════════════════════════════════════════════
# [4] yfinance (미장)
# ══════════════════════════════════════════════

_USD_KRW = 1_350   # 기본값; fetch_usd_krw()로 갱신 가능


def fetch_usd_krw() -> float:
    """yfinance USDKRW=X 실시간 환율 (실패 시 기본값)"""
    global _USD_KRW
    try:
        import yfinance as yf
        hist = yf.Ticker("USDKRW=X").history(period="1d")
        if not hist.empty:
            _USD_KRW = float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"[WARN] 환율 조회 실패: {e} → 기본값 {_USD_KRW} 사용")
    return _USD_KRW


def yf_get_price(ticker: str) -> dict:
    """yfinance로 미국 주식 현재가 조회 (원화 환산)"""
    try:
        rate = fetch_usd_krw()
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d", interval="1m")
        if hist.empty:
            raise ValueError("데이터 없음")
        cur_usd = float(hist["Close"].iloc[-1])
        open_usd = float(hist["Open"].iloc[0])
        high_usd = float(hist["High"].max())
        low_usd  = float(hist["Low"].min())
        return {
            "current_price": int(cur_usd * rate),
            "open_price":    int(open_usd * rate),
            "high_price":    int(high_usd * rate),
            "low_price":     int(low_usd * rate),
            "current_usd":   round(cur_usd, 2),
            "usd_krw":       round(rate, 2),
        }
    except ImportError:
        print("[WARN] yfinance 미설치. pip install yfinance 실행 필요.")
        return mock_get_price(ticker)
    except Exception as e:
        print(f"[WARN] yfinance 조회 실패({ticker}): {e}")
        return mock_get_price(ticker)


def yf_get_price_history(ticker: str, days: int = 30) -> list[float]:
    """yfinance 가격 히스토리 (원화 환산)"""
    try:
        rate = fetch_usd_krw()
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=f"{days}d", interval="1d")
        return [float(c) * rate for c in hist["Close"].tolist()]
    except Exception:
        from technical import generate_mock_price_history
        return generate_mock_price_history(ticker, n=days)


# ══════════════════════════════════════════════
# [5] 통합 인터페이스 (Mock/Real 자동 분기)
# ══════════════════════════════════════════════

def get_price(stock_code: str, session: str = "KR") -> dict:
    from market_adapters import get_adapter
    return get_adapter(session).get_price(stock_code)


def get_prev_day(stock_code: str, session: str = "KR") -> dict:
    if config.MOCK_MODE:
        return mock_get_prev_day(stock_code)
    if session == "KR":
        try:
            return kis_get_prev_day(stock_code)
        except Exception as exc:
            print(f"[WARN] KIS 전일시세 실패({stock_code}): {exc} → Mock 폴백")
            return mock_get_prev_day(stock_code)
    else:
        # yfinance: 전일 데이터 추출
        try:
            import yfinance as yf
            hist = yf.Ticker(stock_code).history(period="5d", interval="1d")
            if len(hist) >= 2:
                prev = hist.iloc[-2]
                return {
                    "prev_high":  int(prev["High"] * _USD_KRW),
                    "prev_low":   int(prev["Low"]  * _USD_KRW),
                    "prev_close": int(prev["Close"] * _USD_KRW),
                }
        except Exception:
            pass
        return mock_get_prev_day(stock_code)


def get_balance(session: str = "KR") -> tuple[int, list[dict]]:
    from market_adapters import get_adapter
    return get_adapter(session).get_balance()


def get_price_history(stock_code: str, session: str = "KR", days: int = 30) -> list[float]:
    """세션별 종가 히스토리 (기술 지표용)"""
    from technical import generate_mock_price_history

    if config.MOCK_MODE:
        return generate_mock_price_history(stock_code, n=days)

    if session == "KR":
        try:
            hist = kis_get_price_history(stock_code, days=days)
            if len(hist) >= config.RSI_PERIOD + 1:
                return hist
        except Exception as e:
            print(f"[WARN] KIS 과거시세 실패({stock_code}): {e} → Mock 폴백")
        return generate_mock_price_history(stock_code, n=days)

    hist = yf_get_price_history(stock_code, days=days)
    if len(hist) >= config.RSI_PERIOD + 1:
        return hist
    return generate_mock_price_history(stock_code, n=days)


# 통합 실행 인터페이스는 order_engine.py로 이전되었습니다.

"""
order_engine.py — 주문 실행 엔진 모듈
(KIS 실전/모의투자 주문 및 미국장/Mock 주문 시뮬레이션)
"""

import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import config
import market_data

KST = ZoneInfo("Asia/Seoul")

# ══════════════════════════════════════════════
# [1] KIS API 주문 (한국장)
# ══════════════════════════════════════════════

def _kis_headers(tr_id: str) -> dict:
    # market_data의 토큰 발급 함수 재사용
    return {
        "Content-Type": "application/json",
        "authorization": f"Bearer {market_data._get_kis_token()}",
        "appkey": config.KIS_APP_KEY,
        "appsecret": config.KIS_APP_SECRET,
        "tr_id": tr_id,
    }


def kis_buy(stock_code: str, qty: int) -> tuple[bool, str]:
    tr_id = "TTTC0802U" if config.IS_REAL_TRADING else "VTTC0802U"
    try:
        res = requests.post(
            f"{config.KIS_URL}/uapi/domestic-stock/v1/trading/order-cash",
            headers=_kis_headers(tr_id),
            json={
                "CANO": config.ACCOUNT_NO, "ACNT_PRDT_CD": config.ACCOUNT_CODE,
                "PDNO": stock_code, "ORD_DVSN": "01", # 시장가(01)
                "ORD_QTY": str(qty), "ORD_UNPR": "0",
            },
            timeout=10,
        )
        res.raise_for_status()
        result = res.json()
        ok = result.get("rt_cd") == "0"
        return ok, result.get("msg1", "성공")
    except Exception as e:
        return False, f"KIS 매수 통신 에러: {e}"


def kis_sell(stock_code: str, qty: int) -> tuple[bool, str]:
    tr_id = "TTTC0801U" if config.IS_REAL_TRADING else "VTTC0801U"
    try:
        res = requests.post(
            f"{config.KIS_URL}/uapi/domestic-stock/v1/trading/order-cash",
            headers=_kis_headers(tr_id),
            json={
                "CANO": config.ACCOUNT_NO, "ACNT_PRDT_CD": config.ACCOUNT_CODE,
                "PDNO": stock_code, "ORD_DVSN": "01", # 시장가(01)
                "ORD_QTY": str(qty), "ORD_UNPR": "0",
            },
            timeout=10,
        )
        res.raise_for_status()
        result = res.json()
        ok = result.get("rt_cd") == "0"
        return ok, result.get("msg1", "성공")
    except Exception as e:
        return False, f"KIS 매도 통신 에러: {e}"


# ══════════════════════════════════════════════
# [2] KIS 해외주식 주문 (미국장)
# ══════════════════════════════════════════════

def _us_exchange(ticker: str) -> str:
    return config.US_STOCKS.get(ticker, {}).get("exchange", "NASD")


def _us_limit_price(ticker: str, side: str) -> str:
    """
    KIS 해외주식은 순수 시장가 미지원 — 지정가(ORD_DVSN=00)로 처리.
    현재가 기준으로 매수는 +2%, 매도는 -2% 여유를 두어 즉시 체결 유도.
    fast_info.last_price가 None일 수 있으므로(장 마감 후) history()로 폴백.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price  # 장중에는 빠름
        if price is None or price <= 0:
            # 장 마감 후 fallback — history 마지막 종가
            hist = stock.history(period="5d", interval="1d")
            if hist.empty:
                return "0"
            price = float(hist["Close"].iloc[-1])
        return f"{price * 1.02:.4f}" if side == "buy" else f"{price * 0.98:.4f}"
    except Exception:
        return "0"


def _kis_us_response_check(res: requests.Response) -> tuple[bool, str]:
    """KIS 응답 파싱 — 500 에러 시 body 메시지 추출"""
    try:
        body = res.json()
        if res.status_code == 200 and body.get("rt_cd") == "0":
            return True, body.get("msg1", "성공")
        msg = body.get("msg1") or body.get("msg_cd") or f"HTTP {res.status_code}"
        return False, f"KIS 거부: {msg.strip()}"
    except Exception:
        return False, f"KIS HTTP {res.status_code}: {res.text[:200]}"


def kis_us_buy(ticker: str, qty: int, limit_price: str | None = None) -> tuple[bool, str]:
    """KIS 해외주식 지정가 매수 (현재가 +2% → 즉시 체결 유도).
    limit_price를 직접 전달하면 yfinance 재조회 생략 (place_manual_order 등에서 사용).
    """
    tr_id = "TTTS1002U" if config.IS_REAL_TRADING else "VTTS1002U"
    price = limit_price if (limit_price and limit_price != "0") else _us_limit_price(ticker, "buy")
    if price == "0":
        return False, f"KIS 해외 매수 실패: {ticker} 가격 조회 불가"
    try:
        res = requests.post(
            f"{config.KIS_URL}/uapi/overseas-stock/v1/trading/order",
            headers=_kis_headers(tr_id),
            json={
                "CANO": config.ACCOUNT_NO,
                "ACNT_PRDT_CD": config.ACCOUNT_CODE,
                "OVRS_EXCG_CD": _us_exchange(ticker),
                "PDNO": ticker,
                "ORD_QTY": str(qty),
                "OVRS_ORD_UNPR": price,
                "ORD_DVSN": "00",
                "ORD_SVR_DVSN": "",
            },
            timeout=15,
        )
        return _kis_us_response_check(res)
    except Exception as e:
        return False, f"KIS 해외 매수 에러: {e}"


def kis_us_sell(ticker: str, qty: int, limit_price: str | None = None) -> tuple[bool, str]:
    """KIS 해외주식 지정가 매도 (현재가 -2% → 즉시 체결 유도).
    limit_price를 직접 전달하면 yfinance 재조회 생략 (place_manual_order 등에서 사용).
    """
    tr_id = "TTTS1001U" if config.IS_REAL_TRADING else "VTTS1001U"
    price = limit_price if (limit_price and limit_price != "0") else _us_limit_price(ticker, "sell")
    if price == "0":
        return False, f"KIS 해외 매도 실패: {ticker} 가격 조회 불가"
    try:
        res = requests.post(
            f"{config.KIS_URL}/uapi/overseas-stock/v1/trading/order",
            headers=_kis_headers(tr_id),
            json={
                "CANO": config.ACCOUNT_NO,
                "ACNT_PRDT_CD": config.ACCOUNT_CODE,
                "OVRS_EXCG_CD": _us_exchange(ticker),
                "PDNO": ticker,
                "ORD_QTY": str(qty),
                "OVRS_ORD_UNPR": price,
                "ORD_DVSN": "00",
                "SLL_TYPE": "00",
                "ORD_SVR_DVSN": "",
            },
            timeout=15,
        )
        return _kis_us_response_check(res)
    except Exception as e:
        return False, f"KIS 해외 매도 에러: {e}"


# ══════════════════════════════════════════════
# [3] Mock 시뮬레이션 주문
# ══════════════════════════════════════════════

def mock_buy(stock_code: str, qty: int, price: int) -> bool:
    all_stocks = {**config.KR_STOCKS, **config.US_STOCKS}
    name = all_stocks.get(stock_code, {}).get("name", stock_code)
    cost = price * qty
    if market_data._mock_cash < cost:
        return False
    market_data._mock_cash -= cost
    if stock_code in market_data._mock_holdings:
        prev = market_data._mock_holdings[stock_code]
        tot_qty = prev["qty"] + qty
        avg = (prev["avg_price"] * prev["qty"] + price * qty) // tot_qty
        market_data._mock_holdings[stock_code].update({"qty": tot_qty, "avg_price": avg})
    else:
        market_data._mock_holdings[stock_code] = {
            "code": stock_code, "name": name,
            "qty": qty, "avg_price": price, "eval_price": price,
        }
    market_data.mock_trade_log.append({
        "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "action": "매수", "name": name, "code": stock_code,
        "qty": qty, "price": price, "amount": cost, "pnl": None,
    })
    return True


def mock_sell(stock_code: str, qty: int, price: int) -> tuple[bool, int]:
    """Returns (success, realized_pnl)"""
    if stock_code not in market_data._mock_holdings:
        return False, 0
    h = market_data._mock_holdings[stock_code]
    sell_qty = min(qty, h["qty"])
    proceed = price * sell_qty
    pnl = (price - h["avg_price"]) * sell_qty
    market_data._mock_cash += proceed

    market_data.mock_trade_log.append({
        "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "action": "매도", "name": h["name"], "code": stock_code,
        "qty": sell_qty, "price": price, "amount": proceed, "pnl": pnl,
    })

    if sell_qty >= h["qty"]:
        del market_data._mock_holdings[stock_code]
    else:
        market_data._mock_holdings[stock_code]["qty"] -= sell_qty
    return True, pnl


# ══════════════════════════════════════════════
# [4] 통합 실행 인터페이스
# ══════════════════════════════════════════════

def execute_buy(stock_code: str, qty: int, price: int, session: str = "KR") -> tuple[bool, str]:
    from market_adapters import get_adapter
    return get_adapter(session).execute_buy(stock_code, qty, price)


def execute_sell(stock_code: str, qty: int, price: int, session: str = "KR") -> tuple[bool, int, str]:
    """Returns (success, realized_pnl, message)"""
    from market_adapters import get_adapter
    return get_adapter(session).execute_sell(stock_code, qty, price)

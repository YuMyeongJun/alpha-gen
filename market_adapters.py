"""
market_adapters.py — 시장별 Mock/KIS/yfinance 어댑터 (Strategy 패턴)

market_data · order_engine 의 if MOCK_MODE 분기를 이 모듈로 집중합니다.
"""

from abc import ABC, abstractmethod

import config
import market_data
import order_engine


class MarketAdapter(ABC):
    """세션별 시세·잔고·주문 통합 인터페이스"""

    @abstractmethod
    def get_price(self, stock_code: str) -> dict:
        ...

    @abstractmethod
    def get_balance(self) -> tuple[int, list[dict]]:
        ...

    @abstractmethod
    def get_price_history(self, stock_code: str, days: int = 30) -> list[float]:
        ...

    @abstractmethod
    def execute_buy(self, stock_code: str, qty: int, price: int) -> tuple[bool, str]:
        ...

    @abstractmethod
    def execute_sell(self, stock_code: str, qty: int, price: int) -> tuple[bool, int, str]:
        ...


class MockAdapter(MarketAdapter):
    def get_price(self, stock_code: str) -> dict:
        return market_data.mock_get_price(stock_code)

    def get_balance(self) -> tuple[int, list[dict]]:
        return market_data.mock_get_balance()

    def get_price_history(self, stock_code: str, days: int = 30) -> list[float]:
        from technical import generate_mock_price_history
        return generate_mock_price_history(stock_code, n=days)

    def execute_buy(self, stock_code: str, qty: int, price: int) -> tuple[bool, str]:
        ok = order_engine.mock_buy(stock_code, qty, price)
        return ok, "Mock 매수 완료" if ok else "Mock 잔고 부족"

    def execute_sell(self, stock_code: str, qty: int, price: int) -> tuple[bool, int, str]:
        ok, pnl = order_engine.mock_sell(stock_code, qty, price)
        return ok, pnl, "Mock 매도 완료" if ok else "Mock 보유수량 없음"


class KisKRAdapter(MarketAdapter):
    def get_price(self, stock_code: str) -> dict:
        return market_data.kis_get_price(stock_code)

    def get_balance(self) -> tuple[int, list[dict]]:
        return market_data.kis_get_balance()

    def get_price_history(self, stock_code: str, days: int = 30) -> list[float]:
        from technical import generate_mock_price_history
        try:
            hist = market_data.kis_get_price_history(stock_code, days=days)
            if len(hist) >= config.RSI_PERIOD + 1:
                return hist
        except Exception:
            pass
        return generate_mock_price_history(stock_code, n=days)

    def execute_buy(self, stock_code: str, qty: int, price: int) -> tuple[bool, str]:
        return order_engine.kis_buy(stock_code, qty)

    def execute_sell(self, stock_code: str, qty: int, price: int) -> tuple[bool, int, str]:
        ok, msg = order_engine.kis_sell(stock_code, qty)
        return ok, 0, msg


def _kis_us_orders_enabled() -> bool:
    return (
        getattr(config, "ENABLE_KIS_US_ORDERS", False)
        and "여기에" not in config.KIS_APP_KEY
    )


class UsYfinanceAdapter(MarketAdapter):
    """미장 시세: yfinance / 주문: KIS 해외주식 또는 Mock"""

    def get_price(self, stock_code: str) -> dict:
        return market_data.yf_get_price(stock_code)

    def get_balance(self) -> tuple[int, list[dict]]:
        # 해외주식 잔고는 해외주식 전용 API로 조회 (국내 잔고 API와 다름)
        if not config.MOCK_MODE:
            try:
                return market_data.kis_get_overseas_balance()
            except Exception:
                pass
        return market_data.mock_get_balance()

    def get_price_history(self, stock_code: str, days: int = 30) -> list[float]:
        from technical import generate_mock_price_history
        hist = market_data.yf_get_price_history(stock_code, days=days)
        if len(hist) >= config.RSI_PERIOD + 1:
            return hist
        return generate_mock_price_history(stock_code, n=days)

    def execute_buy(self, stock_code: str, qty: int, price: int) -> tuple[bool, str]:
        if _kis_us_orders_enabled():
            ok, msg = order_engine.kis_us_buy(stock_code, qty)
            if ok:
                return ok, msg
        ok = order_engine.mock_buy(stock_code, qty, price)
        tag = "KIS 해외" if _kis_us_orders_enabled() else "미국장 모의"
        return ok, f"{tag} 매수 완료" if ok else f"{tag} 매수 실패(잔고 부족)"

    def execute_sell(self, stock_code: str, qty: int, price: int) -> tuple[bool, int, str]:
        if _kis_us_orders_enabled():
            ok, msg = order_engine.kis_us_sell(stock_code, qty)
            if ok:
                return ok, 0, msg
        ok, pnl = order_engine.mock_sell(stock_code, qty, price)
        tag = "KIS 해외" if _kis_us_orders_enabled() else "미국장 모의"
        return ok, pnl, f"{tag} 매도 완료" if ok else f"{tag} 보유수량 없음"


_adapters: dict[str, MarketAdapter] = {}


def get_adapter(session: str = "KR") -> MarketAdapter:
    """세션·모드에 맞는 어댑터 싱글톤 반환"""
    if config.MOCK_MODE:
        key = "MOCK"
        cls = MockAdapter
    elif session == "KR":
        key = "KR"
        cls = KisKRAdapter
    else:
        key = "US"
        cls = UsYfinanceAdapter

    if key not in _adapters:
        _adapters[key] = cls()
    return _adapters[key]


def reset_adapters() -> None:
    """테스트용 어댑터 캐시 초기화"""
    _adapters.clear()

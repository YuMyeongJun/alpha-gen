from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    session: Literal["AUTO", "KR", "US"] = "AUTO"
    force_refresh: bool = False


class AgentCycleRequest(BaseModel):
    session: Literal["AUTO", "KR", "US"] = "AUTO"
    force_refresh: bool = False
    place_orders: bool = True


class WorkerRequest(BaseModel):
    interval_sec: int = Field(default=60, ge=5, le=3600)
    session: Literal["AUTO", "KR", "US"] = "AUTO"
    place_orders: bool = True
    mode: Literal["accumulation"] = "accumulation"
    """`signal` 모드는 P9에서 폐기된 전략이라 스키마에서 제외한다 (spec.md P9/P15)."""


class AccumulationRequest(BaseModel):
    """정기 적립 수동 실행. period 미지정 시 현재 연월(YYYY-MM)을 쓴다."""
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    dry_run: bool = False


class PaperOrderRequest(BaseModel):
    stock_code: str
    session: Literal["KR", "US"]
    side: Literal["buy", "sell"]
    qty: int = Field(ge=1)
    client_order_id: str | None = None


class BacktestRequest(BaseModel):
    stocks: list[str] | None = None
    sentiment_scores: dict[str, int] | None = None
    days: int = Field(default=30, ge=5, le=365)
    initial_cash: int | None = Field(default=None, ge=1)


class EmergencyStopRequest(BaseModel):
    enabled: bool
    reason: str = ""


class PromotionStageRequest(BaseModel):
    stage: Literal["mock", "paper", "shadow", "live_limited", "live_full"]


class AdminActionRequest(BaseModel):
    confirm: bool
    reason: str = Field(min_length=2)


class ManualOrderRequest(BaseModel):
    """UI에서 직접 실행하는 매수/매도 주문 (리스크 휴면 모드 무시, KIS 실행 시도)."""
    stock_code: str
    session: Literal["KR", "US"]
    side: Literal["buy", "sell"]
    qty: int = Field(ge=1)


class ManualPositionRequest(BaseModel):
    """한투 앱 등 외부에서 보유 중인 포지션을 수동으로 등록합니다."""
    stock_code: str
    session: Literal["KR", "US"] = "KR"
    qty: int = Field(ge=1)
    avg_price: int = Field(ge=1, description="평균 매입가 (원)")
    stock_name: str = ""


class AddStockRequest(BaseModel):
    """화면에서 커스텀 종목을 추가할 때 사용."""
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    session: Literal["KR", "US"]
    keywords: list[str] = []
    exchange: Literal["NASD", "NYSE", "AMEX"] = "NASD"
    news_topic: str = ""


class ApiEnvelope(BaseModel):
    status: Literal["ok", "error"]
    data: dict[str, Any]

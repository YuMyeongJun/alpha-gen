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


class ApiEnvelope(BaseModel):
    status: Literal["ok", "error"]
    data: dict[str, Any]

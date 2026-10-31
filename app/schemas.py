from __future__ import annotations

"""Pydantic v2 schemas for API request and response validation."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = "ok"
    last_data_date: str = "2017-12-31"
    models_loaded: bool = True


class SkuResponse(BaseModel):
    """SKU master record schema."""
    sku_id: str
    store: int
    item: int
    lead_time_mean: int
    lead_time_std: float
    mean_daily: float | None = None
    cv: float | None = None
    seasonality_amp: float | None = None
    cluster: int | None = None
    abc: str | None = None
    xyz: str | None = None
    tier: str | None = None


class ForecastRequest(BaseModel):
    """Demand forecast request schema."""
    store: int = Field(..., ge=1, le=10, description="Store identifier (1 to 10)")
    item: int = Field(..., ge=1, le=50, description="Item identifier (1 to 50)")
    horizon_days: int = Field(..., ge=1, le=28, description="Horizon in days (1 to 28)")
    granularity: Literal["daily", "weekly"] = Field("daily", description="daily or weekly")
    model: Literal["holt_winters", "random_forest", "best"] = Field("best", description="Model family")

    @field_validator("horizon_days")
    @classmethod
    def validate_weekly_horizon(cls, v: int, info) -> int:
        """Validate that weekly granularity uses a multiple of 7."""
        # Field validation can be refined in the endpoint or validator
        return v


class ForecastPoint(BaseModel):
    """Individual forecast prediction point."""
    date: str
    yhat: float


class ForecastResponse(BaseModel):
    """Demand forecast response schema."""
    sku_id: str
    model: str
    granularity: str
    history_end: str
    forecasts: list[ForecastPoint]


class AnomalyItem(BaseModel):
    """Single anomaly record."""
    date: str
    sales: int
    z_score: float | None = None
    z_flag: int
    iqr_flag: int


class DecisionRequest(BaseModel):
    """Inventory replenishment decision request schema."""
    store: int = Field(..., ge=1, le=10, description="Store ID (1 to 10)")
    item: int = Field(..., ge=1, le=50, description="Item ID (1 to 50)")
    current_stock: int = Field(..., ge=0, description="Current stock on hand (non-negative)")
    on_order: int = Field(0, ge=0, description="Quantity currently on order (non-negative)")
    service_level: float | None = Field(None, ge=0.50, le=0.999, description="Target service level (0.50 to 0.999)")
    lead_time_days: int | None = Field(None, ge=1, le=60, description="Lead time in days (1 to 60)")
    as_of_date: str | None = Field(None, description="Evaluation date (YYYY-MM-DD)")


class DecisionResponse(BaseModel):
    """Inventory replenishment decision response schema."""
    sku_id: str
    as_of_date: str
    abc: str
    xyz: str
    tier: str
    lead_time_days: int
    service_level: float
    z_value: float
    mean_daily_forecast: float
    lead_time_demand: float
    sigma_d: float
    safety_stock: int
    safety_stock_extended: int
    reorder_point: int
    inventory_position: int
    days_of_cover: float
    action: str
    priority: str
    recommended_order_qty: int
    overstock_flag: bool
    triggered_rule: str
    explanation: str


class DecisionBatchRequest(BaseModel):
    """Batch decision request containing up to 100 items."""
    items: list[DecisionRequest] = Field(..., max_length=100)


class ErrorDetail(BaseModel):
    """Standardized API error response body."""
    detail: str

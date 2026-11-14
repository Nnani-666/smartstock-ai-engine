from __future__ import annotations

"""FastAPI application for SmartStock and the Supply Chain Engine."""

import hmac
import json
import logging
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import (
    create_session,
    get_current_user,
    hash_password,
    make_rate_limiter,
    revoke_session,
    verify_password,
)
from app.config import (
    ALLOWED_ORIGINS,
    API_KEY,
    API_TITLE,
    API_VERSION,
    ENVIRONMENT,
    GEMINI_API_KEY,
    LAST_DATA_DATE,
    METRICS_PATH,
    MODEL_PATH,
    RATE_LIMIT_AI_PER_MIN,
    RATE_LIMIT_AUTH_PER_MIN,
    SEGMENTS_PATH,
)

auth_rate_limiter = make_rate_limiter(RATE_LIMIT_AUTH_PER_MIN, 60)
ai_rate_limiter = make_rate_limiter(RATE_LIMIT_AI_PER_MIN, 60)
from app.db import get_db, get_write_db
from app.schemas import (
    AnomalyItem,
    DecisionBatchRequest,
    DecisionRequest,
    DecisionResponse,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    SkuResponse,
)
from app.services.decision import make_decision
from app.services.forecasting import (
    fit_predict_holt_winters,
    forecast_rf_single_series,
    forecast_seasonal_naive,
)
from app.services.supabase_service import SupabaseAppService

logger = logging.getLogger(__name__)

# State container populated during startup lifespan
app_state: dict[str, Any] = {
    "rf_model": None,
    "metrics": {},
    "segments": {},
    "sku_master_cache": {},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: loads models, metrics, and SKU caches at startup."""
    # 1. Load Random Forest model if present
    if MODEL_PATH.exists():
        try:
            app_state["rf_model"] = joblib.load(MODEL_PATH)
            logger.info("Loaded Random Forest model from %s", MODEL_PATH)
        except Exception as e:
            logger.warning("Could not load model: %s", e)

    # 2. Load metrics if present
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                app_state["metrics"] = json.load(f)
        except Exception as e:
            logger.warning("Could not load metrics: %s", e)

    # 3. Load segments if present
    if SEGMENTS_PATH.exists():
        try:
            with open(SEGMENTS_PATH, "r") as f:
                app_state["segments"] = json.load(f)
        except Exception as e:
            logger.warning("Could not load segments: %s", e)

    yield
    # Shutdown logic
    app_state.clear()


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """Dependency: enforce API key check or authenticated user session when API_KEY is set or in production."""
    from app import config as cfg

    active_api_key = API_KEY if API_KEY is not None else getattr(cfg, "API_KEY", None)
    active_env = ENVIRONMENT if ENVIRONMENT != "development" else getattr(cfg, "ENVIRONMENT", ENVIRONMENT)

    # 1. Direct API key validation
    if active_api_key is not None and x_api_key and hmac.compare_digest(x_api_key, active_api_key):
        return

    # 2. Authenticated user session validation (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        cursor = db.cursor()
        cursor.execute(
            "SELECT user_email, expires_at, revoked FROM app_sessions WHERE token = ?",
            (token,),
        )
        sess = cursor.fetchone()
        if sess and not sess["revoked"]:
            try:
                exp_dt = datetime.fromisoformat(sess["expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                if exp_dt > datetime.now(timezone.utc).replace(tzinfo=None):
                    return
            except Exception as exp_err:
                logger.debug("Failed parsing session expiry: %s", exp_err)

    # 3. Fail closed in production when API_KEY is unconfigured and caller has no valid session
    if active_env == "production" and not active_api_key and not (authorization and authorization.startswith("Bearer ")):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server configuration error: API_KEY is required in production mode.",
        )

    # 4. If API_KEY is configured and neither a valid API key nor a valid session was presented
    if active_api_key is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key / Session Token",
        )


# ----------------------------------------------------------------------
# ANALYTICAL ENGINE API ROUTES
# ----------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    """Liveness check endpoint."""
    return HealthResponse(
        status="ok",
        last_data_date=LAST_DATA_DATE,
        models_loaded=bool(app_state.get("rf_model") is not None),
    )


@app.get("/skus", dependencies=[Depends(verify_api_key)])
def list_skus(
    store: int | None = Query(None, ge=1, le=10),
    item: int | None = Query(None, ge=1, le=50),
    abc: str | None = Query(None),
    xyz: str | None = Query(None),
    tier: str | None = Query(None),
    cluster: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """List SKUs with filtering and pagination."""
    query = "SELECT * FROM sku_master WHERE 1=1"
    params = []

    if store is not None:
        query += " AND store = ?"
        params.append(store)
    if item is not None:
        query += " AND item = ?"
        params.append(item)
    if abc is not None:
        query += " AND abc = ?"
        params.append(abc)
    if xyz is not None:
        query += " AND xyz = ?"
        params.append(xyz)
    if tier is not None:
        query += " AND tier = ?"
        params.append(tier)
    if cluster is not None:
        query += " AND cluster = ?"
        params.append(cluster)

    query += " ORDER BY store, item LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    try:
        cursor = db.cursor()
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        logger.error("DB error in /skus: %s", e)
        raise HTTPException(status_code=500, detail="Internal database error while listing SKUs")


@app.get("/skus/{store}/{item}", dependencies=[Depends(verify_api_key)], response_model=SkuResponse)
def get_sku(store: int, item: int, db: sqlite3.Connection = Depends(get_db)):
    """Retrieve full record for one SKU from sku_master."""
    if store < 1 or store > 10 or item < 1 or item > 50:
        raise HTTPException(status_code=422, detail="Store (1-10) and Item (1-50) bounds violated")

    cursor = db.cursor()
    cursor.execute("SELECT * FROM sku_master WHERE store = ? AND item = ?", (store, item))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU for store {store} item {item} not found")
    return dict(row)


@app.post("/forecast", dependencies=[Depends(verify_api_key)], response_model=ForecastResponse)
def get_forecast(req: ForecastRequest, db: sqlite3.Connection = Depends(get_db)):
    """Generate demand forecast for a single SKU."""
    if req.granularity == "weekly" and (req.horizon_days % 7 != 0):
        raise HTTPException(status_code=422, detail="Weekly granularity requires horizon_days to be a multiple of 7")

    cursor = db.cursor()
    cursor.execute(
        "SELECT date, sales_clean FROM sales WHERE store = ? AND item = ? ORDER BY date",
        (req.store, req.item),
    )
    rows = cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No sales data found for store {req.store} item {req.item}")

    df_hist = pd.DataFrame([dict(r) for r in rows])
    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist["store"] = req.store
    df_hist["item"] = req.item
    history_vals = df_hist["sales_clean"].values.astype(np.float32)

    # Determine chosen model
    chosen_model = req.model
    if chosen_model == "best":
        best_name = app_state.get("metrics", {}).get("forecasting", {}).get("best_model", "random_forest")
        chosen_model = best_name

    # Produce daily forecasts
    if chosen_model == "random_forest" and app_state.get("rf_model") is not None:
        last_dt = df_hist["date"].max()
        daily_preds = forecast_rf_single_series(
            app_state["rf_model"], df_hist, req.horizon_days, req.store, req.item, last_dt
        )
    elif chosen_model == "holt_winters":
        daily_preds = fit_predict_holt_winters(history_vals, req.horizon_days, req.store, req.item)
    elif chosen_model == "random_forest":
        # Fallback if model not loaded
        daily_preds = fit_predict_holt_winters(history_vals, req.horizon_days, req.store, req.item)
    else:
        daily_preds = forecast_seasonal_naive(history_vals, req.horizon_days)

    # Granularity transformation
    start_dt = df_hist["date"].max() + pd.Timedelta(days=1)
    forecast_points: list[ForecastPoint] = []

    if req.granularity == "daily":
        for i in range(req.horizon_days):
            cur_date = (start_dt + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
            forecast_points.append(ForecastPoint(date=cur_date, yhat=round(float(daily_preds[i]), 2)))
    else:
        # Weekly aggregation: sum consecutive 7 days
        num_weeks = req.horizon_days // 7
        for w in range(num_weeks):
            week_sum = float(np.sum(daily_preds[w * 7 : (w + 1) * 7]))
            week_date = (start_dt + pd.Timedelta(days=(w * 7))).strftime("%Y-%m-%d")
            forecast_points.append(ForecastPoint(date=week_date, yhat=round(week_sum, 2)))

    sku_id = f"S{req.store:02d}-I{req.item:02d}"
    return ForecastResponse(
        sku_id=sku_id,
        model=chosen_model,
        granularity=req.granularity,
        history_end=df_hist["date"].max().strftime("%Y-%m-%d"),
        forecasts=forecast_points,
    )


@app.get("/anomalies", dependencies=[Depends(verify_api_key)], response_model=list[AnomalyItem])
def get_anomalies(
    store: int = Query(..., ge=1, le=10),
    item: int = Query(..., ge=1, le=50),
    start: str | None = Query(None),
    end: str | None = Query(None),
    method: Literal["z", "iqr", "any"] = Query("any"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve historical anomaly log for a specific SKU."""
    query = "SELECT date, sales, z_score, z_flag, iqr_flag FROM sales WHERE store = ? AND item = ?"
    params: list[Any] = [store, item]

    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)

    if method == "z":
        query += " AND z_flag = 1"
    elif method == "iqr":
        query += " AND iqr_flag = 1"
    else:
        query += " AND (z_flag = 1 OR iqr_flag = 1)"

    query += " ORDER BY date"
    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [
        AnomalyItem(
            date=r["date"],
            sales=r["sales"],
            z_score=round(r["z_score"], 2) if r["z_score"] is not None else None,
            z_flag=r["z_flag"],
            iqr_flag=r["iqr_flag"],
        )
        for r in rows
    ]


@app.post("/decision", dependencies=[Depends(verify_api_key)], response_model=DecisionResponse)
def get_decision(req: DecisionRequest, db: sqlite3.Connection = Depends(get_db)):
    """Generate inventory replenishment decision for a single SKU."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM sku_master WHERE store = ? AND item = ?", (req.store, req.item))
    sku_row = cursor.fetchone()
    if not sku_row:
        raise HTTPException(status_code=404, detail=f"SKU for store {req.store} item {req.item} not found")

    sku_dict = dict(sku_row)

    # Lead time demand forecast
    lt_mean = sku_dict.get("lead_time_mean", 7)
    L = req.lead_time_days if req.lead_time_days is not None else max(1, round(lt_mean))

    # Fetch last 90 days of sales_clean up to as_of_date
    as_of = req.as_of_date or LAST_DATA_DATE
    cursor.execute(
        "SELECT date, sales_clean FROM sales WHERE store = ? AND item = ? AND date <= ? ORDER BY date DESC LIMIT 90",
        (req.store, req.item, as_of),
    )
    recent_rows = cursor.fetchall()
    if not recent_rows:
        df_recent = pd.DataFrame([{"date": as_of, "sales_clean": 10.0}])
    else:
        df_recent = pd.DataFrame([dict(r) for r in reversed(recent_rows)])

    # Forecast next L days
    history_arr = df_recent["sales_clean"].values.astype(np.float32)
    lt_forecast = fit_predict_holt_winters(history_arr, L, req.store, req.item)

    decision_res = make_decision(
        store=req.store,
        item=req.item,
        current_stock=req.current_stock,
        on_order=req.on_order,
        sku_info=sku_dict,
        recent_history=df_recent,
        lead_time_forecast=lt_forecast,
        service_level=req.service_level,
        lead_time_days=req.lead_time_days,
        as_of_date=req.as_of_date,
    )
    return DecisionResponse(**decision_res)


@app.post("/decision/batch", dependencies=[Depends(verify_api_key)], response_model=list[DecisionResponse])
def get_decision_batch(req: DecisionBatchRequest, db: sqlite3.Connection = Depends(get_db)):
    """Batch replenishment decisions for up to 100 items."""
    if len(req.items) > 100:
        raise HTTPException(status_code=422, detail="Batch size exceeds maximum limit of 100 items")

    results: list[DecisionResponse] = []
    for item_req in req.items:
        res = get_decision(item_req, db)
        results.append(res)
    return results


@app.get("/segments/summary", dependencies=[Depends(verify_api_key)])
def get_segments_summary():
    """Retrieve segmentation summary metrics."""
    return app_state.get("segments", {})


@app.get("/metrics", dependencies=[Depends(verify_api_key)])
def get_metrics():
    """Retrieve model evaluation metrics."""
    return app_state.get("metrics", {})


# ----------------------------------------------------------------------
# LIVE SMARTSTOCK APPLICATION ROUTES (SUPABASE INTEGRATION)
# ----------------------------------------------------------------------

_supabase_service: SupabaseAppService | None = None

def get_supabase_service() -> SupabaseAppService:
    """Return lazily initialized Supabase service."""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseAppService()
    return _supabase_service


@app.get("/api/v1/products")
def api_list_products(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve live products list from Supabase (authenticated and tenant-scoped)."""
    try:
        shop_id = current_user.get("id") or current_user.get("user_id")
        return get_supabase_service().list_products(shop_id=shop_id, status=status, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/insights")
def api_list_insights(
    active_only: bool = True,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve live inventory insights from Supabase (authenticated and tenant-scoped)."""
    try:
        shop_id = current_user.get("id") or current_user.get("user_id")
        return get_supabase_service().list_insights(shop_id=shop_id, active_only=active_only)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/purchase-orders")
def api_list_purchase_orders(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve purchase orders from Supabase (authenticated and tenant-scoped)."""
    try:
        shop_id = current_user.get("id") or current_user.get("user_id")
        return get_supabase_service().list_purchase_orders(shop_id=shop_id)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/shop")
def api_get_shop(
    code: str = "STORE-402",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve current shop profile from Supabase (authenticated)."""
    try:
        shop = get_supabase_service().get_shop_by_code(code)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


# ----------------------------------------------------------------------
# USER AUTHENTICATION & MULTI-TENANT ISOLATED STORE REGISTER
# ----------------------------------------------------------------------

# Backwards compatibility alias for tests and legacy callers
hash_pw = hash_password


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    store_name: str
    phone: str = ""
    manager: str = "Store Owner"


class UserLoginRequest(BaseModel):
    email: str
    password: str


class ProductCreateRequest(BaseModel):
    user_email: str | None = None
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    sku: str | None = None
    description: str = ""
    unit_price: float = Field(0.0, ge=0)
    unit_cost: float = Field(0.0, ge=0)
    stock_on_hand: int = Field(0, ge=0)
    safety_stock: int = Field(2, ge=0)
    reorder_point: int = Field(5, ge=0)
    lead_time_days: int = Field(3, ge=0)
    supplier: str = "Metro Wholesale"
    category_name: str = "Groceries & Household"


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    sku: str | None = None
    description: str | None = None
    unit_price: float | None = Field(None, ge=0)
    unit_cost: float | None = Field(None, ge=0)
    stock_on_hand: int | None = Field(None, ge=0)
    safety_stock: int | None = Field(None, ge=0)
    reorder_point: int | None = Field(None, ge=0)
    lead_time_days: int | None = Field(None, ge=0)
    supplier: str | None = None
    category_name: str | None = None


class BulkStockRequest(BaseModel):
    product_ids: list[str] = Field(..., min_length=1, max_length=200)
    delta: int = Field(..., ge=-10000, le=10000)


class BulkDeleteRequest(BaseModel):
    product_ids: list[str] = Field(..., min_length=1, max_length=500)


class BulkImportRequest(BaseModel):
    products: list[ProductCreateRequest] = Field(..., min_length=1, max_length=1000)


class SupplierCreateRequest(BaseModel):
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    category: str | None = Field("General Wholesale", max_length=100)
    phone: str | None = Field("+91 98000 00000", max_length=50)
    email: str | None = Field("orders@distributor.in", max_length=100)
    hub: str | None = Field("Regional Logistics Hub", max_length=200)
    lead_time_days: int = Field(3, ge=1, le=120)
    is_verified: bool = True


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    hub: str | None = Field(None, max_length=200)
    lead_time_days: int | None = Field(None, ge=1, le=120)
    is_verified: bool | None = None


class POCreateRequest(BaseModel):
    user_email: str | None = None
    id: str | None = None
    po_number: str | None = Field(None, max_length=100)
    supplier: str = Field(..., min_length=1, max_length=200)
    status: Literal["ordered", "in_transit", "draft", "pending"] = "ordered"
    total_amount: float | None = Field(None, ge=0)
    items: list[dict[str, Any]]


class POStatusUpdateRequest(BaseModel):
    status: Literal["ordered", "in_transit", "cancelled"]


class SaleRecordRequest(BaseModel):
    user_email: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    sale_amount: float | None = Field(None, ge=0)
    units: int = Field(1, le=100000)
    unit_cost: float | None = Field(None, ge=0)
    timestamp: str | None = None
    idempotency_key: str | None = Field(None, max_length=128)


class AIAssistantRequest(BaseModel):
    prompt: str | None = Field(None, max_length=1000)
    context_type: str = "store_summary"


@app.post("/api/v1/auth/register", dependencies=[Depends(auth_rate_limiter)])
def register_user(req: UserRegisterRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Register a new merchant account with PBKDF2 password security and isolated data namespace."""
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    cursor = db.cursor()
    cursor.execute("SELECT id FROM app_users WHERE email = ?", (clean_email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    store = req.store_name.strip() or "My Store"

    cursor.execute(
        """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, clean_email, pw_hash, store, req.phone, req.manager, now_iso),
    )
    db.commit()

    token = create_session(user_id, clean_email, db)

    return {
        "status": "ok",
        "token": token,
        "user": {
            "id": user_id,
            "email": clean_email,
            "store": store,
            "phone": req.phone,
            "manager": req.manager,
        },
    }


@app.post("/api/v1/auth/login", dependencies=[Depends(auth_rate_limiter)])
def login_user(req: UserLoginRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Authenticate merchant user with strict password verification and zero-downtime PBKDF2 rehash."""
    clean_email = req.email.strip().lower()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM app_users WHERE email = ?", (clean_email,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_dict = dict(row)
    is_valid, needs_rehash = verify_password(req.password, user_dict["password_hash"])
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Seamless login-time password migration: upgrade legacy hash to PBKDF2
    if needs_rehash:
        new_hash = hash_password(req.password)
        cursor.execute("UPDATE app_users SET password_hash = ? WHERE id = ?", (new_hash, user_dict["id"]))
        db.commit()
        logger.info("Migrated password hash for %s to PBKDF2-HMAC-SHA256", clean_email)

    token = create_session(user_dict["id"], user_dict["email"], db)

    return {
        "status": "ok",
        "token": token,
        "user": {
            "id": user_dict["id"],
            "email": user_dict["email"],
            "store": user_dict["store_name"],
            "phone": user_dict["phone"],
            "manager": user_dict["manager"],
        },
    }


@app.post("/api/v1/auth/logout")
def logout_user(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Revoke active session token upon user sign out."""
    token = current_user.get("token")
    if token:
        revoke_session(token, db)
    return {"status": "ok", "message": "Successfully signed out."}


@app.get("/api/v1/auth/me")
def get_auth_me(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve profile of authenticated merchant user."""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "store": current_user["store_name"],
        "phone": current_user["phone"],
        "manager": current_user["manager"],
    }


@app.get("/api/v1/user/products")
def get_user_products(
    email: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """List products belonging to the authenticated merchant catalog."""
    clean_email = current_user["email"]
    if email and email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot access another merchant's product catalog.",
        )
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM app_products WHERE user_email = ? ORDER BY created_at DESC",
        (clean_email,),
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/user/products")
def add_user_product(
    req: ProductCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Add a product to the authenticated user's isolated catalog."""
    clean_email = current_user["email"]
    if req.user_email and req.user_email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot create products in another merchant's catalog.",
        )

    cursor = db.cursor()
    prod_id = str(uuid.uuid4())
    if req.id:
        cursor.execute("SELECT user_email FROM app_products WHERE id = ?", (req.id,))
        if not cursor.fetchone():
            prod_id = req.id
    sku = req.sku or f"SKU-{str(uuid.uuid4())[:6].upper()}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    status_str = "out_of_stock" if req.stock_on_hand <= 0 else ("low_stock" if req.stock_on_hand <= req.reorder_point else "active")

    cursor.execute(
        """INSERT INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, category_name, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (prod_id, clean_email, sku, req.name, req.description, req.unit_price, req.unit_cost, req.stock_on_hand, req.safety_stock, req.reorder_point, req.lead_time_days, req.supplier, req.category_name, status_str, now_iso),
    )
    db.commit()

    return {
        "id": prod_id,
        "user_email": clean_email,
        "sku": sku,
        "name": req.name,
        "unit_price": req.unit_price,
        "unit_cost": req.unit_cost,
        "stock_on_hand": req.stock_on_hand,
        "reorder_point": req.reorder_point,
        "supplier": req.supplier,
        "category_name": req.category_name,
        "status": status_str,
    }


@app.put("/api/v1/user/products/{product_id}")
def update_user_product(
    product_id: str,
    req: ProductUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Update product fields strictly within authenticated merchant's catalog."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM app_products WHERE id = ? AND user_email = ?", (product_id, clean_email))
        row = cursor.fetchone()
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Product not found in merchant inventory")

        cur = dict(row)
        new_name = req.name if req.name is not None else cur["name"]
        new_sku = req.sku if req.sku is not None else cur["sku"]
        new_desc = req.description if req.description is not None else cur["description"]
        new_price = req.unit_price if req.unit_price is not None else cur["unit_price"]
        new_cost = req.unit_cost if req.unit_cost is not None else cur["unit_cost"]
        new_stock = req.stock_on_hand if req.stock_on_hand is not None else int(cur["stock_on_hand"])
        new_ss = req.safety_stock if req.safety_stock is not None else int(cur["safety_stock"])
        new_rop = req.reorder_point if req.reorder_point is not None else int(cur["reorder_point"])
        new_lt = req.lead_time_days if req.lead_time_days is not None else int(cur["lead_time_days"])
        new_supp = req.supplier if req.supplier is not None else cur["supplier"]
        new_cat = req.category_name if req.category_name is not None else (cur.get("category_name") or "Groceries & Household")
        new_status = "out_of_stock" if new_stock <= 0 else ("low_stock" if new_stock <= new_rop else "active")

        cursor.execute(
            """UPDATE app_products
               SET name = ?, sku = ?, description = ?, unit_price = ?, unit_cost = ?,
                   stock_on_hand = ?, safety_stock = ?, reorder_point = ?, lead_time_days = ?,
                   supplier = ?, category_name = ?, status = ?
               WHERE id = ? AND user_email = ?""",
            (new_name, new_sku, new_desc, new_price, new_cost, new_stock, new_ss, new_rop, new_lt, new_supp, new_cat, new_status, product_id, clean_email),
        )
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Product update error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during product update")

    cursor.execute("SELECT * FROM app_products WHERE id = ? AND user_email = ?", (product_id, clean_email))
    return dict(cursor.fetchone())


@app.delete("/api/v1/user/products/{product_id}")
def delete_user_product(
    product_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Delete a product strictly from the authenticated merchant's catalog."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    cursor.execute("DELETE FROM app_products WHERE id = ? AND user_email = ?", (product_id, clean_email))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Product not found in merchant inventory")
    db.commit()
    return {"status": "ok", "deleted_id": product_id}


@app.post("/api/v1/user/products/bulk-stock")
def bulk_update_stock(
    req: BulkStockRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Atomically adjust stock on hand across multiple products owned by authenticated merchant."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    updated_ids: list[str] = []
    unique_ids = list(dict.fromkeys(req.product_ids))
    try:
        cursor.execute("BEGIN IMMEDIATE")
        for pid in unique_ids:
            cursor.execute(
                """UPDATE app_products
                   SET stock_on_hand = stock_on_hand + ?,
                       status = CASE WHEN stock_on_hand + ? <= 0 THEN 'out_of_stock'
                                     WHEN stock_on_hand + ? <= reorder_point THEN 'low_stock'
                                     ELSE 'active' END
                   WHERE id = ? AND user_email = ? AND stock_on_hand + ? >= 0""",
                (req.delta, req.delta, req.delta, pid, clean_email, req.delta),
            )
            if cursor.rowcount == 1:
                updated_ids.append(pid)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Bulk stock update error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during bulk stock update")

    return {"status": "ok", "updated_count": len(updated_ids), "updated_ids": updated_ids}


@app.post("/api/v1/user/products/bulk-delete")
def bulk_delete_products(
    req: BulkDeleteRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Atomically delete multiple products belonging to the authenticated merchant."""
    clean_email = current_user["email"]
    unique_ids = list(dict.fromkeys(req.product_ids))
    cursor = db.cursor()
    deleted_ids: list[str] = []
    try:
        cursor.execute("BEGIN IMMEDIATE")
        for pid in unique_ids:
            cursor.execute(
                "DELETE FROM app_products WHERE id = ? AND user_email = ?",
                (pid, clean_email),
            )
            if cursor.rowcount == 1:
                deleted_ids.append(pid)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Bulk delete error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during bulk delete")

    return {"status": "ok", "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@app.post("/api/v1/user/products/bulk-import")
def bulk_import_products(
    req: BulkImportRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Atomically import multiple products into the authenticated user's catalog."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    imported_ids: list[str] = []
    errors: list[str] = []

    try:
        cursor.execute("BEGIN IMMEDIATE")
        for idx, p in enumerate(req.products):
            if not p.name or not p.name.strip():
                errors.append(f"Row {idx + 1}: Name cannot be empty")
                continue
            prod_id = p.id or str(uuid.uuid4())
            sku = p.sku or f"SKU-{str(uuid.uuid4())[:6].upper()}"
            stock = max(0, p.stock_on_hand)
            rop = p.reorder_point if p.reorder_point is not None else 5
            status_str = "out_of_stock" if stock <= 0 else ("low_stock" if stock <= rop else "active")
            cursor.execute(
                """INSERT OR REPLACE INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, category_name, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prod_id, clean_email, sku, p.name.strip(), p.description or "", p.unit_price, p.unit_cost, stock, p.safety_stock, rop, p.lead_time_days, p.supplier or "General Wholesale", p.category_name or "Groceries & Household", status_str, now_iso),
            )
            imported_ids.append(prod_id)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Bulk import error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during bulk import")

    return {"status": "ok", "imported_count": len(imported_ids), "imported_ids": imported_ids, "errors": errors}


@app.get("/api/v1/user/purchase-orders")
def get_user_pos(
    email: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """List purchase orders for the authenticated merchant."""
    clean_email = current_user["email"]
    if email and email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot view another merchant's purchase orders.",
        )
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM app_purchase_orders WHERE user_email = ? ORDER BY created_at DESC",
        (clean_email,),
    )
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["items"] = json.loads(d["items_json"])
        except Exception:
            d["items"] = []
        results.append(d)
    return results


@app.post("/api/v1/user/purchase-orders")
def create_user_po(
    req: POCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Create a new purchase order for the authenticated merchant with idempotency support."""
    clean_email = current_user["email"]
    if req.user_email and req.user_email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot create purchase orders for another merchant.",
        )

    # Validate items
    for it in req.items:
        if not isinstance(it, dict):
            raise HTTPException(status_code=400, detail="Each purchase order item must be an object")
        units = it.get("units") if it.get("units") is not None else it.get("quantity")
        if units is not None:
            try:
                int(units)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Item quantity must be a valid number")

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        if req.id:
            cursor.execute("SELECT * FROM app_purchase_orders WHERE id = ?", (req.id,))
            existing = cursor.fetchone()
            if existing:
                if existing["user_email"] != clean_email:
                    db.rollback()
                    raise HTTPException(status_code=403, detail="Forbidden: Purchase order ID collision.")
                d = dict(existing)
                try:
                    d["items"] = json.loads(d["items_json"])
                except Exception:
                    d["items"] = []
                d["replayed"] = True
                db.rollback()
                return d
            po_id = req.id
        else:
            po_id = str(uuid.uuid4())

        po_num = req.po_number or f"PO-{datetime.now(timezone.utc).strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        if req.total_amount is not None:
            total_amt = float(req.total_amount)
        else:
            total_amt = sum(
                float(it.get("quantity") or it.get("units") or 0) * float(it.get("unit_cost") or it.get("cost") or 0)
                for it in req.items
            )

        now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        cursor.execute(
            """INSERT INTO app_purchase_orders (id, user_email, po_number, supplier, status, total_amount, items_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (po_id, clean_email, po_num, req.supplier, req.status, total_amt, json.dumps(req.items), now_iso),
        )
        db.commit()
    except HTTPException:
        raise
    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Purchase order with this ID already exists")
    except Exception as exc:
        db.rollback()
        logger.error("Create PO error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during purchase order creation")

    return {
        "id": po_id,
        "po_number": po_num,
        "status": req.status,
        "supplier": req.supplier,
        "total_amount": total_amt,
        "items": req.items,
        "created_at": now_iso,
        "replayed": False,
    }


@app.patch("/api/v1/user/purchase-orders/{po_id}/status")
def update_user_po_status(
    po_id: str,
    req: POStatusUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Update status (ordered, in_transit, cancelled) of an uncompleted purchase order."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT status FROM app_purchase_orders WHERE id = ? AND user_email = ?",
            (po_id, clean_email),
        )
        row = cursor.fetchone()
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if row["status"] in ("completed", "cancelled"):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot change status of a {row['status']} purchase order",
            )

        cursor.execute(
            "UPDATE app_purchase_orders SET status = ? WHERE id = ? AND user_email = ? AND status NOT IN ('completed', 'cancelled')",
            (req.status, po_id, clean_email),
        )
        if cursor.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Purchase order status conflict")
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("PO status update error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error during PO status update")
    return {"status": "ok", "po_id": po_id, "new_status": req.status}


@app.post("/api/v1/user/purchase-orders/{po_id}/receive")
def receive_user_po(
    po_id: str,
    email: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Receive purchase order: increments stock_on_hand in authenticated user's inventory."""
    clean_email = current_user["email"]
    if email and email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot inward another merchant's purchase order.",
        )

    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT * FROM app_purchase_orders WHERE id = ? AND user_email = ?",
            (po_id, clean_email),
        )
        row = cursor.fetchone()
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Purchase order not found")

        po_dict = dict(row)
        if po_dict["status"] == "completed":
            db.rollback()
            return {"status": "already_completed", "message": "PO already inwarded"}
        if po_dict["status"] == "cancelled":
            db.rollback()
            raise HTTPException(status_code=400, detail="Cannot receive a cancelled purchase order")

        now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        cursor.execute(
            """UPDATE app_purchase_orders
               SET status = 'completed', inwarded_at = ?
               WHERE id = ? AND user_email = ? AND status NOT IN ('completed', 'cancelled')""",
            (now_iso, po_id, clean_email),
        )
        if cursor.rowcount != 1:
            db.rollback()
            return {"status": "already_completed", "message": "PO already inwarded"}

        items = []
        try:
            items = json.loads(po_dict["items_json"])
        except Exception:
            pass

        # Increment stock in app_products for each valid item
        for it in items:
            try:
                units = int(it.get("units") or it.get("quantity") or 0)
            except (ValueError, TypeError):
                units = 0
            if units <= 0:
                continue
            p_name = it.get("name") or it.get("item")
            p_id = it.get("product_id")
            if p_id:
                cursor.execute(
                    """UPDATE app_products
                       SET stock_on_hand = stock_on_hand + ?,
                           status = CASE WHEN stock_on_hand + ? <= 0 THEN 'out_of_stock' WHEN stock_on_hand + ? <= reorder_point THEN 'low_stock' ELSE 'active' END
                       WHERE id = ? AND user_email = ?""",
                    (units, units, units, p_id, clean_email),
                )
            elif p_name:
                cursor.execute(
                    """UPDATE app_products
                       SET stock_on_hand = stock_on_hand + ?,
                           status = CASE WHEN stock_on_hand + ? <= 0 THEN 'out_of_stock' WHEN stock_on_hand + ? <= reorder_point THEN 'low_stock' ELSE 'active' END
                       WHERE name = ? AND user_email = ?""",
                    (units, units, units, p_name, clean_email),
                )

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error inwarding PO %s: %s", po_id, e)
        raise HTTPException(status_code=500, detail="Database error during PO receipt")

    return {"status": "ok", "po_id": po_id, "inwarded_at": now_iso}


@app.get("/api/v1/user/suppliers")
def get_user_suppliers(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """List suppliers for the authenticated merchant."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM app_suppliers WHERE user_email = ? ORDER BY created_at ASC",
        (clean_email,),
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/user/suppliers")
def create_user_supplier(
    req: SupplierCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Create a new supplier for the authenticated merchant."""
    clean_email = current_user["email"]
    supp_id = req.id or f"supp-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """INSERT INTO app_suppliers (id, user_email, name, category, phone, email, hub, lead_time_days, is_verified, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (supp_id, clean_email, req.name.strip(), req.category or "General Wholesale", req.phone or "+91 98000 00000", req.email or "orders@distributor.in", req.hub or "Regional Logistics Hub", req.lead_time_days, 1 if req.is_verified else 0, now_iso),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier with this ID already exists")
    except Exception as exc:
        db.rollback()
        logger.error("Create supplier error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error creating supplier")

    cursor.execute("SELECT * FROM app_suppliers WHERE id = ? AND user_email = ?", (supp_id, clean_email))
    return dict(cursor.fetchone())


@app.put("/api/v1/user/suppliers/{supplier_id}")
def update_user_supplier(
    supplier_id: str,
    req: SupplierUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Update supplier details for the authenticated merchant."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM app_suppliers WHERE id = ? AND user_email = ?", (supplier_id, clean_email))
        row = cursor.fetchone()
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Supplier not found")
        cur = dict(row)
        new_name = req.name.strip() if req.name is not None else cur["name"]
        new_cat = req.category if req.category is not None else cur["category"]
        new_phone = req.phone if req.phone is not None else cur["phone"]
        new_email = req.email if req.email is not None else cur["email"]
        new_hub = req.hub if req.hub is not None else cur["hub"]
        new_lt = req.lead_time_days if req.lead_time_days is not None else cur["lead_time_days"]
        new_ver = (1 if req.is_verified else 0) if req.is_verified is not None else cur["is_verified"]

        cursor.execute(
            """UPDATE app_suppliers
               SET name = ?, category = ?, phone = ?, email = ?, hub = ?, lead_time_days = ?, is_verified = ?
               WHERE id = ? AND user_email = ?""",
            (new_name, new_cat, new_phone, new_email, new_hub, new_lt, new_ver, supplier_id, clean_email),
        )
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Update supplier error: %s", exc)
        raise HTTPException(status_code=500, detail="Database error updating supplier")

    cursor.execute("SELECT * FROM app_suppliers WHERE id = ? AND user_email = ?", (supplier_id, clean_email))
    return dict(cursor.fetchone())


@app.delete("/api/v1/user/suppliers/{supplier_id}")
def delete_user_supplier(
    supplier_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Delete a supplier for the authenticated merchant without corrupting historical POs."""
    clean_email = current_user["email"]
    cursor = db.cursor()
    cursor.execute("DELETE FROM app_suppliers WHERE id = ? AND user_email = ?", (supplier_id, clean_email))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.commit()
    return {"status": "ok", "deleted_id": supplier_id}


@app.post("/api/v1/user/sales")
def record_user_sale(
    req: SaleRecordRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_write_db),
):
    """Record a sale with atomic stock verification, Decimal pricing, and unit_cost."""
    clean_email = current_user["email"]
    if req.user_email and req.user_email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot record sales for another merchant.",
        )
    if req.units <= 0:
        raise HTTPException(status_code=400, detail="Sale units must be greater than zero")

    # Validate timestamp if provided and normalize to naive UTC ISO-8601
    if req.timestamp:
        try:
            parsed_ts = datetime.fromisoformat(req.timestamp.replace("Z", "+00:00"))
            if parsed_ts.tzinfo is not None:
                parsed_ts = parsed_ts.astimezone(timezone.utc).replace(tzinfo=None)
            sale_timestamp = parsed_ts.isoformat()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. ISO-8601 required.")
    else:
        sale_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    if not req.product_id and not req.product_name:
        raise HTTPException(status_code=400, detail="Either product_id or product_name must be provided")

    cursor = db.cursor()
    sale_id = str(uuid.uuid4())
    try:
        cursor.execute("BEGIN IMMEDIATE")

        # Idempotency check inside write transaction to prevent TOCTOU races
        if req.idempotency_key:
            cursor.execute(
                "SELECT id, sale_amount, units FROM app_sales WHERE idempotency_key = ? AND user_email = ?",
                (req.idempotency_key, clean_email),
            )
            existing = cursor.fetchone()
            if existing:
                db.rollback()
                return {
                    "status": "ok",
                    "sale_id": existing["id"],
                    "replayed": True,
                    "message": "Sale already processed",
                }

        # Look up product inside write transaction for fresh price/cost/stock
        if req.product_id:
            cursor.execute(
                "SELECT * FROM app_products WHERE id = ? AND user_email = ?",
                (req.product_id, clean_email),
            )
        else:
            cursor.execute(
                "SELECT * FROM app_products WHERE name = ? AND user_email = ?",
                (req.product_name, clean_email),
            )

        prod_row = cursor.fetchone()
        if not prod_row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Product not found in user inventory")

        prod = dict(prod_row)
        current_stock = int(prod["stock_on_hand"])
        if current_stock < req.units:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock on hand: requested {req.units} units, but only {current_stock} available.",
            )

        unit_price_dec = Decimal(str(prod["unit_price"] or 0))
        calc_amount = (unit_price_dec * Decimal(req.units)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        final_amount = float(calc_amount)
        final_cost = prod["unit_cost"] if prod["unit_cost"] is not None else req.unit_cost
        prod_name = prod["name"]

        # Atomic conditional stock deduction (prevents TOCTOU race conditions)
        cursor.execute(
            """UPDATE app_products
               SET stock_on_hand = stock_on_hand - ?,
                   status = CASE WHEN stock_on_hand - ? <= 0 THEN 'out_of_stock'
                                 WHEN stock_on_hand - ? <= reorder_point THEN 'low_stock'
                                 ELSE 'active' END
               WHERE id = ? AND user_email = ? AND stock_on_hand >= ?""",
            (req.units, req.units, req.units, prod["id"], clean_email, req.units),
        )
        if cursor.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Insufficient stock on hand: concurrent inventory update prevented overselling.",
            )

        cursor.execute(
            "SELECT stock_on_hand FROM app_products WHERE id = ? AND user_email = ?",
            (prod["id"], clean_email),
        )
        updated_row = cursor.fetchone()
        new_stock = int(updated_row["stock_on_hand"]) if updated_row else 0

        # Insert sale transaction
        cursor.execute(
            """INSERT INTO app_sales (id, user_email, product_id, product_name, sale_amount, units, unit_cost, timestamp, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sale_id, clean_email, prod["id"], prod_name, final_amount, req.units, final_cost, sale_timestamp, req.idempotency_key),
        )
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Transaction failed during sale recording: %s", e)
        raise HTTPException(status_code=500, detail="Database transaction failed during sale")

    return {
        "status": "ok",
        "sale_id": sale_id,
        "product_name": prod_name,
        "units": req.units,
        "sale_amount": final_amount,
        "unit_cost": final_cost,
        "remaining_stock": new_stock,
    }


@app.get("/api/v1/user/sales")
def get_user_sales(
    email: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """List sales for the authenticated merchant without arbitrary truncation."""
    clean_email = current_user["email"]
    if email and email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot view another merchant's sales.",
        )
    cursor = db.cursor()
    query = "SELECT * FROM app_sales WHERE user_email = ?"
    params = [clean_email]

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/user/sales/summary")
def get_sales_summary(
    email: str | None = Query(None),
    date: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return aggregated daily/period sales summary for authenticated merchant including revenue and profit."""
    clean_email = current_user["email"]
    if email and email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot view another merchant's sales summary.",
        )
    cursor = db.cursor()
    query = "SELECT * FROM app_sales WHERE user_email = ?"
    params = [clean_email]

    if date:
        escaped_date = date.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query += " AND timestamp LIKE ? ESCAPE '\\'"
        params.append(f"{escaped_date}%")

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_rev_dec = Decimal("0.00")
    total_cost_dec = Decimal("0.00")
    total_units = 0
    cost_available = True

    for r in rows:
        units = int(r["units"] or 0)
        total_units += units
        sale_amt = Decimal(str(r["sale_amount"] or 0))
        total_rev_dec += sale_amt

        if r["unit_cost"] is not None:
            unit_cost_dec = Decimal(str(r["unit_cost"]))
            total_cost_dec += (unit_cost_dec * Decimal(units))
        else:
            cost_available = False

    total_rev = float(total_rev_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if cost_available:
        total_cost = float(total_cost_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        gross_profit = float((total_rev_dec - total_cost_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        margin_pct = (
            float(((Decimal(str(gross_profit)) / total_rev_dec) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            if total_rev > 0
            else 0.0
        )
    else:
        total_cost = None
        gross_profit = None
        margin_pct = None

    return {
        "revenue": total_rev,
        "total_units": total_units,
        "transaction_count": len(rows),
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "gross_margin_pct": margin_pct,
        "cost_available": cost_available,
    }


from app.services.assistant_intelligence import (
    build_grounded_store_context,
    generate_local_heuristic_response,
)
from app.services.gemini_router import router as gemini_router


@app.post("/api/v1/ai/assistant", dependencies=[Depends(ai_rate_limiter)])
def ai_assistant_endpoint(
    req: AIAssistantRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Secure server-side AI assistant proxy with multi-model failover.

    1. Reads GEMINI_API_KEY securely from server environment.
    2. Centralizes model selection: Primary (gemini-3.5-flash-lite), Secondary (gemini-3.1-flash-lite).
    3. Scopes context strictly to the authenticated merchant's data.
    4. Automatically fails over to secondary model on quota/rate limits.
    5. Fallbacks gracefully to intent-aware local heuristic engine if all models fail.
    """
    clean_email = current_user["email"]
    cursor = db.cursor()

    # Query only the authenticated merchant's products
    cursor.execute("SELECT * FROM app_products WHERE user_email = ? ORDER BY name ASC", (clean_email,))
    products = [dict(r) for r in cursor.fetchall()]

    # Query only the authenticated merchant's sales
    cursor.execute("SELECT * FROM app_sales WHERE user_email = ? ORDER BY timestamp DESC LIMIT 50", (clean_email,))
    sales = [dict(r) for r in cursor.fetchall()]

    # Query merchant purchase orders
    cursor.execute("SELECT * FROM app_purchase_orders WHERE user_email = ? ORDER BY created_at DESC LIMIT 10", (clean_email,))
    orders = [dict(r) for r in cursor.fetchall()]

    # Query suppliers
    cursor.execute("SELECT * FROM app_suppliers WHERE user_email = ? OR user_email IS NULL ORDER BY name ASC", (clean_email,))
    suppliers = [dict(r) for r in cursor.fetchall()]

    store_name = current_user.get("store_name", "My Store")
    user_prompt = (req.prompt or "").strip() or "Provide a 3-bullet store operations and inventory health summary."

    # Build grounded store context
    ctx = build_grounded_store_context(
        products=products,
        sales=sales,
        orders=orders,
        suppliers=suppliers,
        store_name=store_name,
        user_email=clean_email,
    )

    gemini_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not gemini_key:
        return generate_local_heuristic_response(user_prompt, ctx, fallback_reason="key_unset")

    # Retrieve models not currently on daily or RPM cooldown
    eligible_models = gemini_router.get_eligible_models()
    if not eligible_models:
        logger.warning("All Gemini models currently in cooldown; using local fallback")
        return generate_local_heuristic_response(user_prompt, ctx, fallback_reason="all_models_quota_exhausted")

    # Build system instruction with anti-hallucination rules and intent guidance
    system_instruction = (
        f"You are SmartStock AI Assistant, an expert, practical retail inventory and operations advisor for Indian kirana storekeeper '{store_name}' ({clean_email}).\n\n"
        "GROUNDED STORE TRUTH (AUTHENTICATED TENANT DATA):\n"
        "Active Catalog & Current Inventory:\n" + ("\n".join(ctx["catalog_lines"]) if ctx["catalog_lines"] else "No products registered.") + "\n\n"
        "Recent Sales Highlights:\n" + ("\n".join(ctx["sales_lines"]) if ctx["sales_lines"] else "No recent sales recorded.") + f"\nTotal recorded revenue: ₹{ctx['total_sales_amt']:,.2f} across {len(sales)} transaction(s).\n\n"
        "Pending Purchase Orders (In-Transit):\n" + ("\n".join(ctx["pending_po_lines"]) if ctx["pending_po_lines"] else "No active purchase orders.") + "\n\n"
        "Verified Suppliers:\n" + ("\n".join(ctx["supplier_lines"]) if ctx["supplier_lines"] else "No suppliers registered.") + "\n\n"
        "Seasonal & Demand Context:\n"
        "- High-cyclicality retail patterns: Kirana staples (Atta, Oil, Rice, Spices, Biscuits) experience strong weekend surges (7-day seasonality).\n"
        "- Festive demand assumption: In Indian retail, cooking oils, flours, ghee, sweets, and packaged biscuits often surge during major festivals. (Note: Treat festive demand surge percentages as planning assumptions requiring merchant verification; do not cite fabricated historical facts.)\n\n"
        "CRITICAL OPERATING RULES:\n"
        "1. Ground all recommendations STRICTLY in the storekeeper's actual catalog, inventory numbers, sales, and supplier data above.\n"
        "2. NEVER invent, hallucinate, or fabricate product names, prices, stock levels, or supplier details not listed above.\n"
        "3. Answer practically, concisely, and supportively in clear shopkeeper-friendly language.\n"
        "4. For greetings ('Hi', 'Hello'): Respond with a warm, natural shopkeeper greeting and offer assistance. DO NOT output an unsolicited inventory health report or out-of-stock warning.\n"
        "5. For urgent replenishment queries: Rank products by actual urgency (stock on hand vs ROP, lead time). Check pending in-transit purchase orders and explicitly note them so the merchant does not double-order.\n"
        "6. For stockout prevention: Provide 3 concrete, distinct, actionable steps based on the actual inventory data.\n"
        "7. For sales/revenue: Rank products using actual recorded sales transactions.\n"
        "8. For slow-moving items: Identify products in the catalog with zero or low recent sales.\n"
        "9. For suppliers: Direct the merchant to the specific registered supplier, phone number, and lead time.\n"
        "10. If the requested information is not present in store records, state so politely rather than guessing."
    )

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1500,
        },
    }

    import httpx

    last_failure_reason = "upstream_failure"

    for model_id in eligible_models:
        try:
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
            with httpx.Client(transport=transport, timeout=12.0) as client:
                resp = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                    headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if text:
                        gemini_router.record_success(model_id)
                        return {
                            "status": "ok",
                            "source": "gemini",
                            "model": model_id,
                            "store_name": store_name,
                            "analysis": text.strip(),
                            "metrics": {
                                "total_products": ctx["total_products"],
                                "out_of_stock": len(ctx["out_of_stock"]),
                                "low_stock": len(ctx["low_stock"]),
                                "recent_sales_amount": ctx["total_sales_amt"],
                            },
                        }

                # Classify error and record cooldown
                resp_json = {}
                try:
                    resp_json = resp.json()
                except Exception:
                    pass

                cat, cooldown = gemini_router.classify_error(resp.status_code, resp_json)
                gemini_router.record_failure(model_id, cat, cooldown)
                last_failure_reason = cat

                # If auth failure, do not try next model with same invalid credentials
                if cat == "auth_failure":
                    logger.warning("Gemini authentication failure (HTTP %d); aborting failover", resp.status_code)
                    return generate_local_heuristic_response(user_prompt, ctx, fallback_reason="auth_failure")

                logger.warning("Gemini model %s failed (%s); failing over to next eligible model", model_id, cat)

        except httpx.TimeoutException:
            gemini_router.record_failure(model_id, "timeout", 15.0)
            last_failure_reason = "timeout"
            logger.warning("Gemini model %s timed out (>12.0s); failing over", model_id)
        except Exception as exc:
            cat, cooldown = gemini_router.classify_error(500, None, exc=exc)
            gemini_router.record_failure(model_id, cat, cooldown)
            last_failure_reason = cat
            logger.warning("Gemini model %s exception (%s); failing over", model_id, type(exc).__name__)

    # All models failed -> activate local heuristic engine
    return generate_local_heuristic_response(user_prompt, ctx, fallback_reason=last_failure_reason)


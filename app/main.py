from __future__ import annotations

"""FastAPI application for SmartStock and the Supply Chain Engine."""

import hmac
import json
import logging
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


def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    """Dependency: enforce API key check when API_KEY is set or in production."""
    if ENVIRONMENT == "production" and not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server configuration error: API_KEY is required in production mode.",
        )
    if API_KEY is not None and (not x_api_key or not hmac.compare_digest(x_api_key, API_KEY)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
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


@app.get("/api/v1/products", dependencies=[Depends(get_current_user)])
def api_list_products(status: str | None = None, limit: int = 50, offset: int = 0):
    """Retrieve live products list from Supabase (authenticated)."""
    try:
        return get_supabase_service().list_products(status=status, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/insights", dependencies=[Depends(get_current_user)])
def api_list_insights(active_only: bool = True):
    """Retrieve live inventory insights from Supabase (authenticated)."""
    try:
        return get_supabase_service().list_insights(active_only=active_only)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/purchase-orders", dependencies=[Depends(get_current_user)])
def api_list_purchase_orders():
    """Retrieve purchase orders from Supabase (authenticated)."""
    try:
        return get_supabase_service().list_purchase_orders()
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/shop", dependencies=[Depends(get_current_user)])
def api_get_shop(code: str = "STORE-402"):
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


class POCreateRequest(BaseModel):
    user_email: str | None = None
    po_number: str = Field(..., min_length=1, max_length=100)
    supplier: str = Field(..., min_length=1, max_length=200)
    status: str = "ordered"
    total_amount: float = Field(..., ge=0)
    items: list[dict[str, Any]]


class SaleRecordRequest(BaseModel):
    user_email: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    sale_amount: float | None = Field(None, ge=0)
    units: int = 1
    unit_cost: float | None = Field(None, ge=0)
    timestamp: str | None = None
    idempotency_key: str | None = None


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
    sku = req.sku or f"SKU-{str(uuid.uuid4())[:6].upper()}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    status_str = "out_of_stock" if req.stock_on_hand <= 0 else ("low_stock" if req.stock_on_hand <= req.reorder_point else "active")

    cursor.execute(
        """INSERT INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (prod_id, clean_email, sku, req.name, req.description, req.unit_price, req.unit_cost, req.stock_on_hand, req.safety_stock, req.reorder_point, req.lead_time_days, req.supplier, status_str, now_iso),
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
        "status": status_str,
    }


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
    """Create a new purchase order for the authenticated merchant."""
    clean_email = current_user["email"]
    if req.user_email and req.user_email.strip().lower() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot create purchase orders for another merchant.",
        )

    cursor = db.cursor()
    po_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    cursor.execute(
        """INSERT INTO app_purchase_orders (id, user_email, po_number, supplier, status, total_amount, items_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (po_id, clean_email, req.po_number, req.supplier, req.status, req.total_amount, json.dumps(req.items), now_iso),
    )
    db.commit()

    return {
        "id": po_id,
        "po_number": req.po_number,
        "status": req.status,
        "supplier": req.supplier,
        "total_amount": req.total_amount,
        "items": req.items,
        "created_at": now_iso,
    }


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
            units = int(it.get("units") or it.get("quantity") or 0)
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

    cursor = db.cursor()

    # Idempotency check
    if req.idempotency_key:
        cursor.execute(
            "SELECT id, sale_amount, units FROM app_sales WHERE idempotency_key = ? AND user_email = ?",
            (req.idempotency_key, clean_email),
        )
        existing = cursor.fetchone()
        if existing:
            return {
                "status": "ok",
                "sale_id": existing["id"],
                "replayed": True,
                "message": "Sale already processed",
            }

    # Validate timestamp if provided
    if req.timestamp:
        try:
            datetime.fromisoformat(req.timestamp.replace("Z", "+00:00"))
            sale_timestamp = req.timestamp
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. ISO-8601 required.")
    else:
        sale_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    # Look up product in user's catalog
    if req.product_id:
        cursor.execute(
            "SELECT * FROM app_products WHERE id = ? AND user_email = ?",
            (req.product_id, clean_email),
        )
    elif req.product_name:
        cursor.execute(
            "SELECT * FROM app_products WHERE name = ? AND user_email = ?",
            (req.product_name, clean_email),
        )
    else:
        raise HTTPException(status_code=400, detail="Either product_id or product_name must be provided")

    prod_row = cursor.fetchone()
    if not prod_row:
        raise HTTPException(status_code=404, detail="Product not found in user inventory")

    prod = dict(prod_row)
    current_stock = int(prod["stock_on_hand"])

    # Strict overselling pre-check
    if current_stock < req.units:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock on hand: requested {req.units} units, but only {current_stock} available.",
        )

    # Decimal price calculation
    unit_price_dec = Decimal(str(prod["unit_price"] or 0))
    calc_amount = (unit_price_dec * Decimal(req.units)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final_amount = float(calc_amount)

    # Historical cost basis
    final_cost = prod["unit_cost"] if prod["unit_cost"] is not None else req.unit_cost

    sale_id = str(uuid.uuid4())
    prod_name = prod["name"]

    try:
        cursor.execute("BEGIN IMMEDIATE")
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


@app.post("/api/v1/ai/assistant", dependencies=[Depends(ai_rate_limiter)])
def ai_assistant_endpoint(
    req: AIAssistantRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Secure server-side AI assistant proxy.

    Reads GEMINI_API_KEY securely from server environment.
    Scopes context strictly to the authenticated merchant's data.
    Provides intelligent local heuristic fallback if Gemini API is unreachable or key is unset.
    """
    clean_email = current_user["email"]
    cursor = db.cursor()

    # Query only the authenticated merchant's products
    cursor.execute("SELECT * FROM app_products WHERE user_email = ?", (clean_email,))
    products = [dict(r) for r in cursor.fetchall()]

    # Query only the authenticated merchant's sales
    cursor.execute("SELECT * FROM app_sales WHERE user_email = ? ORDER BY timestamp DESC LIMIT 50", (clean_email,))
    sales = [dict(r) for r in cursor.fetchall()]

    total_prods = len(products)
    out_of_stock = sum(1 for p in products if p.get("stock_on_hand", 0) <= 0)
    low_stock = sum(1 for p in products if 0 < p.get("stock_on_hand", 0) <= p.get("reorder_point", 5))
    total_sales_amt = sum(float(s.get("sale_amount", 0)) for s in sales)
    store_name = current_user.get("store_name", "My Store")

    def build_local_fallback() -> dict[str, Any]:
        advice_points = []
        if out_of_stock > 0:
            advice_points.append(f"Immediate Action: {out_of_stock} product(s) are completely out of stock. Place replenishment orders.")
        if low_stock > 0:
            advice_points.append(f"Replenishment Warning: {low_stock} product(s) have reached reorder thresholds.")
        if not advice_points:
            advice_points.append("All inventory levels are currently in a healthy operational state.")
        if total_sales_amt > 0:
            advice_points.append(f"Recent revenue recorded: ₹{total_sales_amt:,.2f} across {len(sales)} transaction(s).")
        return {
            "status": "ok",
            "source": "local_heuristic",
            "store_name": store_name,
            "analysis": " • ".join(advice_points),
            "metrics": {
                "total_products": total_prods,
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "recent_sales_amount": total_sales_amt,
            },
        }

    gemini_key = GEMINI_API_KEY
    if not gemini_key:
        return build_local_fallback()

    try:
        import httpx
        system_context = (
            f"You are the AI retail advisor for store '{store_name}'. "
            f"Active catalog: {total_prods} products. "
            f"Out of stock: {out_of_stock}. Low stock: {low_stock}. "
            f"Recent sales revenue: ₹{total_sales_amt:,.2f}. "
            "Provide 2-3 concise, actionable bullet points for the storekeeper in plain business language."
        )
        user_prompt = req.prompt or "Provide a 3-bullet store operations and inventory health summary."

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {
                        "parts": [{"text": system_context}]
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_prompt}],
                        }
                    ],
                },
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
                    return {
                        "status": "ok",
                        "source": "gemini-2.5-flash",
                        "store_name": store_name,
                        "analysis": text.strip(),
                        "metrics": {
                            "total_products": total_prods,
                            "out_of_stock": out_of_stock,
                            "low_stock": low_stock,
                            "recent_sales_amount": total_sales_amt,
                        },
                    }
    except Exception as exc:
        logger.warning("Gemini server proxy call failed (%s); using local heuristic fallback", type(exc).__name__)

    return build_local_fallback()


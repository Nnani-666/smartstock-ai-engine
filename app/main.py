from __future__ import annotations

"""FastAPI application for SmartStock and the Supply Chain Engine."""

import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    ALLOWED_ORIGINS,
    API_KEY,
    API_TITLE,
    API_VERSION,
    LAST_DATA_DATE,
    METRICS_PATH,
    MODEL_PATH,
    SEGMENTS_PATH,
)
from app.db import get_db
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
    """Dependency: enforce API key check if API_KEY environment variable is set."""
    if API_KEY is not None and (not x_api_key or x_api_key != API_KEY):
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
        raise HTTPException(status_code=500, detail=str(e))


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
def api_list_products(status: str | None = None, limit: int = 50, offset: int = 0):
    """Retrieve live products list from Supabase."""
    try:
        return get_supabase_service().list_products(status=status, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/insights")
def api_list_insights(active_only: bool = True):
    """Retrieve live inventory insights from Supabase."""
    try:
        return get_supabase_service().list_insights(active_only=active_only)
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/purchase-orders")
def api_list_purchase_orders():
    """Retrieve purchase orders from Supabase."""
    try:
        return get_supabase_service().list_purchase_orders()
    except ValueError as e:
        raise HTTPException(status_code=503, detail="Supabase not configured: " + str(e))


@app.get("/api/v1/shop")
def api_get_shop(code: str = "STORE-402"):
    """Retrieve current shop profile from Supabase."""
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

import hashlib
import uuid
from datetime import datetime
from pydantic import BaseModel
from app.db import get_write_db

def hash_pw(password: str) -> str:
    """Return SHA-256 hash of password with static salt."""
    salt = "smartstock_secret_salt_2026"
    return hashlib.sha256(f"{salt}_{password}".encode()).hexdigest()

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
    user_email: str
    name: str
    sku: str | None = None
    description: str = ""
    unit_price: float = 0.0
    unit_cost: float = 0.0
    stock_on_hand: int = 0
    safety_stock: int = 2
    reorder_point: int = 5
    lead_time_days: int = 3
    supplier: str = "Metro Wholesale"

class POCreateRequest(BaseModel):
    user_email: str
    po_number: str
    supplier: str
    status: str = "ordered"
    total_amount: float
    items: list[dict[str, Any]]

class SaleRecordRequest(BaseModel):
    user_email: str
    product_id: str | None = None
    product_name: str | None = None
    sale_amount: float | None = None
    units: int = 1
    unit_cost: float | None = None
    timestamp: str | None = None
    idempotency_key: str | None = None


@app.post("/api/v1/auth/register")
def register_user(req: UserRegisterRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Register a new merchant account with isolated data namespace."""
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

    cursor = db.cursor()
    cursor.execute("SELECT id FROM app_users WHERE email = ?", (clean_email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")

    user_id = str(uuid.uuid4())
    pw_hash = hash_pw(req.password)
    now_iso = datetime.utcnow().isoformat()
    store = req.store_name.strip() or "My Store"

    cursor.execute(
        """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, clean_email, pw_hash, store, req.phone, req.manager, now_iso),
    )
    db.commit()

    token = hashlib.sha256(f"{user_id}_{clean_email}_{datetime.utcnow().strftime('%Y-%m-%d')}".encode()).hexdigest()

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


@app.post("/api/v1/auth/login")
def login_user(req: UserLoginRequest, db: sqlite3.Connection = Depends(get_db)):
    """Authenticate merchant user with strict password verification."""
    clean_email = req.email.strip().lower()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM app_users WHERE email = ?", (clean_email,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Account not found. Please register your store first.")

    user_dict = dict(row)
    pw_hash = hash_pw(req.password)
    if user_dict["password_hash"] != pw_hash:
        raise HTTPException(status_code=401, detail="Incorrect password. Access denied.")

    token = hashlib.sha256(f"{user_dict['id']}_{user_dict['email']}_{datetime.utcnow().strftime('%Y-%m-%d')}".encode()).hexdigest()

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


@app.get("/api/v1/auth/me")
def get_auth_me(
    authorization: str | None = Header(None),
    email: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """Retrieve profile of authenticated merchant user."""
    clean_email = email.strip().lower() if email else None
    if not clean_email and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        cursor = db.cursor()
        cursor.execute("SELECT * FROM app_users")
        for u in cursor.fetchall():
            expected = hashlib.sha256(f"{u['id']}_{u['email']}_{datetime.utcnow().strftime('%Y-%m-%d')}".encode()).hexdigest()
            if token == expected:
                clean_email = u["email"]
                break

    if not clean_email:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication credentials")

    cursor = db.cursor()
    cursor.execute("SELECT * FROM app_users WHERE email = ?", (clean_email,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user_dict = dict(row)
    return {
        "id": user_dict["id"],
        "email": user_dict["email"],
        "store": user_dict["store_name"],
        "phone": user_dict["phone"],
        "manager": user_dict["manager"],
    }


@app.get("/api/v1/user/products")
def get_user_products(email: str = Query(...), db: sqlite3.Connection = Depends(get_db)):
    """List products belonging to the specified merchant."""
    clean_email = email.strip().lower()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM app_products WHERE user_email = ? ORDER BY created_at DESC",
        (clean_email,),
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/user/products")
def add_user_product(req: ProductCreateRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Add a product to the user's isolated catalog."""
    clean_email = req.user_email.strip().lower()
    cursor = db.cursor()
    prod_id = str(uuid.uuid4())
    sku = req.sku or f"SKU-{str(uuid.uuid4())[:6].upper()}"
    now_iso = datetime.utcnow().isoformat()
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
def get_user_pos(email: str = Query(...), db: sqlite3.Connection = Depends(get_db)):
    """List purchase orders for a merchant."""
    clean_email = email.strip().lower()
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
def create_user_po(req: POCreateRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Create a new purchase order for the merchant."""
    clean_email = req.user_email.strip().lower()
    cursor = db.cursor()
    po_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()

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
def receive_user_po(po_id: str, email: str = Query(...), db: sqlite3.Connection = Depends(get_write_db)):
    """Receive purchase order: increments stock_on_hand in user's inventory catalog."""
    clean_email = email.strip().lower()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM app_purchase_orders WHERE id = ? AND user_email = ?",
        (po_id, clean_email),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    po_dict = dict(row)
    if po_dict["status"] == "completed":
        return {"status": "already_completed", "message": "PO already inwarded"}
    if po_dict["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot receive a cancelled purchase order")

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

    now_iso = datetime.utcnow().isoformat()
    cursor.execute(
        "UPDATE app_purchase_orders SET status = 'completed', inwarded_at = ? WHERE id = ?",
        (now_iso, po_id),
    )
    db.commit()

    return {"status": "ok", "po_id": po_id, "inwarded_at": now_iso}


@app.post("/api/v1/user/sales")
def record_user_sale(req: SaleRecordRequest, db: sqlite3.Connection = Depends(get_write_db)):
    """Record a sale with atomic stock verification, Decimal pricing, and unit_cost."""
    clean_email = req.user_email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Valid user email required")
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
        sale_timestamp = datetime.utcnow().isoformat()

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

    # Strict overselling check: reject entire sale when quantity exceeds stock
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
        # Atomic stock deduction
        new_stock = current_stock - req.units
        rop = int(prod["reorder_point"]) if prod["reorder_point"] is not None else 0
        new_status = "out_of_stock" if new_stock <= 0 else ("low_stock" if new_stock <= rop else "active")

        cursor.execute(
            "UPDATE app_products SET stock_on_hand = ?, status = ? WHERE id = ? AND user_email = ?",
            (new_stock, new_status, prod["id"], clean_email),
        )

        # Insert sale transaction
        cursor.execute(
            """INSERT INTO app_sales (id, user_email, product_id, product_name, sale_amount, units, unit_cost, timestamp, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sale_id, clean_email, prod["id"], prod_name, final_amount, req.units, final_cost, sale_timestamp, req.idempotency_key),
        )
        db.commit()
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
    email: str = Query(...),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """List sales for a merchant without arbitrary truncation."""
    clean_email = email.strip().lower()
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
    email: str = Query(...),
    date: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return aggregated daily/period sales summary including revenue, units, and gross profit."""
    clean_email = email.strip().lower()
    cursor = db.cursor()
    query = "SELECT * FROM app_sales WHERE user_email = ?"
    params = [clean_email]

    if date:
        query += " AND timestamp LIKE ?"
        params.append(f"{date}%")

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

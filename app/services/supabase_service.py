from __future__ import annotations

"""Supabase database client and live application business operations service."""

import logging
from typing import Any

from app.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from supabase import Client, create_client

logger = logging.getLogger(__name__)

# Server-side Supabase client with service-role permissions
_supabase_admin_client: Client | None = None


def get_supabase_admin() -> Client:
    """Return singleton administrative Supabase client."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured in environment")
        _supabase_admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_admin_client


class SupabaseAppService:
    """Business operations adapter for the live SmartStock application."""

    def __init__(self, client: Client | None = None):
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_admin()
        return self._client

    # 1. Shops & Settings
    def get_shop_by_code(self, store_code: str = "STORE-402") -> dict[str, Any] | None:
        """Retrieve shop record by unique store code."""
        try:
            res = self.client.table("shops").select("*").eq("store_code", store_code).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error("Error fetching shop by code %s: %s", store_code, e)
            return None

    # 2. Products
    def list_products(
        self,
        shop_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List products with pagination and optional status filter."""
        try:
            query = self.client.table("products").select("*, categories(name), suppliers(name)")
            if shop_id:
                query = query.eq("shop_id", shop_id)
            if status:
                query = query.eq("status", status)
            query = query.range(offset, offset + limit - 1).order("created_at", desc=False)
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error("Error listing products: %s", e)
            return []

    def get_product_by_id(self, product_id: str) -> dict[str, Any] | None:
        """Get product details by UUID."""
        try:
            res = self.client.table("products").select("*, categories(name), suppliers(name)").eq("id", product_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error("Error getting product %s: %s", product_id, e)
            return None

    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        """Get product by application SKU string."""
        try:
            res = self.client.table("products").select("*").eq("sku", sku).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            logger.error("Error getting product by sku %s: %s", sku, e)
            return None

    # 3. Stock Movements
    def record_stock_movement(
        self,
        shop_id: str,
        product_id: str,
        movement_type: str,
        quantity: int,
        notes: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        """Record an auditable stock adjustment and update product on-hand stock transactionally."""
        product = self.get_product_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        current = int(product.get("stock_on_hand", 0))
        new_stock = max(0, current + quantity)

        movement_record = {
            "shop_id": shop_id,
            "product_id": product_id,
            "movement_type": movement_type,
            "quantity": quantity,
            "previous_stock": current,
            "new_stock": new_stock,
            "notes": notes,
            "reference_id": reference_id,
        }

        # Insert movement
        self.client.table("stock_movements").insert(movement_record).execute()

        # Update product stock and status
        status = "out_of_stock" if new_stock == 0 else ("low_stock" if new_stock <= product.get("reorder_point", 0) else "active")
        self.client.table("products").update({
            "stock_on_hand": new_stock,
            "status": status,
        }).eq("id", product_id).execute()

        return movement_record

    # 4. Insights & Recommendations
    def list_insights(self, shop_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        """List inventory insights and AI replenishment alerts."""
        try:
            query = self.client.table("inventory_insights").select("*, products(name, sku, stock_on_hand, reorder_point)")
            if shop_id:
                query = query.eq("shop_id", shop_id)
            if active_only:
                query = query.eq("status", "active")
            query = query.order("priority", desc=False)
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error("Error listing insights: %s", e)
            return []

    # 5. Purchase Orders
    def list_purchase_orders(self, shop_id: str | None = None) -> list[dict[str, Any]]:
        """List purchase orders with supplier information."""
        try:
            query = self.client.table("purchase_orders").select("*, suppliers(name)")
            if shop_id:
                query = query.eq("shop_id", shop_id)
            query = query.order("created_at", desc=True)
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error("Error listing purchase orders: %s", e)
            return []

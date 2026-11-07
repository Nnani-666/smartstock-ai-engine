from __future__ import annotations

"""Database connection management and SQLite schema definitions."""

import sqlite3
from collections.abc import Generator

from app.config import DB_PATH


def get_db_connection(read_only: bool = True) -> sqlite3.Connection:
    """Create and return a SQLite connection.
    
    Args:
        read_only: If True, opens SQLite in read-only URI mode.
        
    Returns:
        sqlite3.Connection with Row factory configured.
    """
    if read_only:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency for obtaining a read-only database connection per request."""
    conn = get_db_connection(read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def get_write_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency for obtaining a read-write database connection per request."""
    conn = get_db_connection(read_only=False)
    try:
        yield conn
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Initialize the analytical database schema and indexes.
    
    Args:
        conn: Optional existing connection. If None, creates a read-write connection.
    """
    close_after = False
    if conn is None:
        conn = get_db_connection(read_only=False)
        close_after = True

    try:
        cursor = conn.cursor()
        
        # 1. Sales Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                store INTEGER NOT NULL,
                item INTEGER NOT NULL,
                date TEXT NOT NULL,
                sales INTEGER NOT NULL,
                sales_clean REAL,
                z_score REAL,
                z_flag INTEGER DEFAULT 0,
                iqr_flag INTEGER DEFAULT 0,
                is_anomaly INTEGER DEFAULT 0,
                PRIMARY KEY (store, item, date)
            );
        """)

        # 2. SKU Master Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sku_master (
                sku_id TEXT PRIMARY KEY,
                store INTEGER NOT NULL,
                item INTEGER NOT NULL,
                lead_time_mean INTEGER NOT NULL,
                lead_time_std REAL NOT NULL,
                mean_daily REAL,
                cv REAL,
                seasonality_amp REAL,
                cluster INTEGER,
                abc TEXT,
                xyz TEXT,
                tier TEXT,
                UNIQUE (store, item)
            );
        """)

        # 3. Application User Accounts Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                store_name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                manager TEXT DEFAULT 'Store Owner',
                created_at TEXT NOT NULL
            );
        """)

        # 4. User-Scoped Inventory Products Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_products (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                unit_price REAL DEFAULT 0,
                unit_cost REAL DEFAULT 0,
                stock_on_hand INTEGER DEFAULT 0,
                safety_stock INTEGER DEFAULT 2,
                reorder_point INTEGER DEFAULT 5,
                lead_time_days INTEGER DEFAULT 3,
                supplier TEXT DEFAULT 'Metro Wholesale',
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            );
        """)

        # 5. User-Scoped Purchase Orders Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_purchase_orders (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                po_number TEXT NOT NULL,
                supplier TEXT NOT NULL,
                status TEXT NOT NULL,
                total_amount REAL DEFAULT 0,
                items_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                inwarded_at TEXT
            );
        """)

        # 6. User-Scoped Sales Register Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_sales (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                product_id TEXT,
                product_name TEXT NOT NULL,
                sale_amount REAL DEFAULT 0,
                units INTEGER DEFAULT 1,
                unit_cost REAL DEFAULT NULL,
                timestamp TEXT NOT NULL,
                idempotency_key TEXT
            );
        """)

        # Migration: ensure unit_cost and idempotency_key columns exist on older tables
        cursor.execute("PRAGMA table_info(app_sales);")
        sales_cols = [row[1] for row in cursor.fetchall()]
        if "unit_cost" not in sales_cols:
            cursor.execute("ALTER TABLE app_sales ADD COLUMN unit_cost REAL DEFAULT NULL;")
        if "idempotency_key" not in sales_cols:
            cursor.execute("ALTER TABLE app_sales ADD COLUMN idempotency_key TEXT;")

        # Indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_store_item ON sales(store, item);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sku_master_store_item ON sku_master(store, item);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_products_user ON app_products(user_email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_po_user ON app_purchase_orders(user_email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_sales_user ON app_sales(user_email);")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_app_sales_idempotency ON app_sales(idempotency_key) WHERE idempotency_key IS NOT NULL;")


        # Seed default demo account if not exists
        cursor.execute("SELECT id FROM app_users WHERE email = 'owner@sharmakirana.in'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
                VALUES ('usr_demo_sharma', 'owner@sharmakirana.in', 'b73b0cb9ce1bd549546be76ff0e852971cc059875ae795cc06ab8a6740eee527', 'Sharma Kirana Store', '+91 98765 43210', 'Store Owner', datetime('now'))
            """)
            demo_products = [
                ('p_demo_1', 'owner@sharmakirana.in', 'KIR-AASH-05', 'Aashirvaad Superior MP Sharbati Atta (5kg)', 'Premium whole wheat flour', 245.0, 210.0, 24, 6, 10, 3, 'ITC Limited', 'active', "datetime('now')"),
                ('p_demo_2', 'owner@sharmakirana.in', 'KIR-FORT-01', 'Fortune Sunlite Refined Sunflower Oil (1L)', 'Refined edible oil pouch', 145.0, 125.0, 8, 8, 12, 4, 'Adani Wilmar', 'active', "datetime('now')"),
                ('p_demo_3', 'owner@sharmakirana.in', 'KIR-PARL-01', 'Parle-G Gold Glucose Biscuits (1kg)', 'High volume glucose tea biscuit pack', 120.0, 105.0, 22, 6, 10, 3, 'Parle Products', 'active', "datetime('now')"),
                ('p_demo_4', 'owner@sharmakirana.in', 'KIR-DETT-250', 'Dettol Antiseptic Liquid (250ml)', 'Hygiene and first aid antiseptic liquid', 130.0, 112.0, 12, 4, 6, 5, 'Reckitt Benckiser', 'active', "datetime('now')"),
                ('p_demo_5', 'owner@sharmakirana.in', 'KIR-SURF-01', 'Surf Excel Quick Wash Detergent (1kg)', 'Premium stain removal laundry powder', 150.0, 132.0, 16, 5, 8, 4, 'Hindustan Unilever', 'active', "datetime('now')"),
            ]
            for p in demo_products:
                cursor.execute("""
                    INSERT INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, p[:13])

        conn.commit()
    finally:
        if close_after:
            conn.close()

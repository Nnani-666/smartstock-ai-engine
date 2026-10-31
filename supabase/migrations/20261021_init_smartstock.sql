-- SmartStock Supabase Schema & Initial Migration
-- Target: Supabase PostgreSQL (Project: txpvoqdecsjpmklelxdb)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. PROFILES (Extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'merchant',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. SHOPS / STORES (Multi-shop isolation)
CREATE TABLE IF NOT EXISTS public.shops (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    store_code TEXT UNIQUE NOT NULL,
    description TEXT,
    address TEXT,
    currency TEXT DEFAULT 'USD',
    owner_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    settings JSONB DEFAULT '{"auto_reorder": false, "default_service_level": 0.95, "lead_time_days": 7}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. SHOP MEMBERS & ROLES
CREATE TABLE IF NOT EXISTS public.shop_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'manager', 'merchant', 'staff', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, user_id)
);

-- 4. CATEGORIES
CREATE TABLE IF NOT EXISTS public.categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, name)
);

-- 5. SUPPLIERS
CREATE TABLE IF NOT EXISTS public.suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    lead_time_days INTEGER DEFAULT 7,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'preferred')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. PRODUCTS (Inventory Master)
CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category_id UUID REFERENCES public.categories(id) ON DELETE SET NULL,
    supplier_id UUID REFERENCES public.suppliers(id) ON DELETE SET NULL,
    barcode TEXT,
    unit_cost NUMERIC(12, 2) DEFAULT 0.00,
    unit_price NUMERIC(12, 2) DEFAULT 0.00,
    stock_on_hand INTEGER DEFAULT 0 CHECK (stock_on_hand >= 0),
    stock_on_order INTEGER DEFAULT 0 CHECK (stock_on_order >= 0),
    safety_stock INTEGER DEFAULT 0,
    reorder_point INTEGER DEFAULT 0,
    lead_time_days INTEGER DEFAULT 7,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'low_stock', 'out_of_stock', 'archived')),
    abc_class TEXT CHECK (abc_class IN ('A', 'B', 'C')),
    xyz_class TEXT CHECK (xyz_class IN ('X', 'Y', 'Z')),
    tier TEXT CHECK (tier IN ('Strategic', 'Core', 'Tail')),
    analytical_sku_id TEXT, -- Adapter mapping to supply_chain.db SKU (e.g. S01-I01)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, sku)
);

-- 7. STOCK MOVEMENTS (Auditable inventory ledger)
CREATE TABLE IF NOT EXISTS public.stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('IN', 'OUT', 'ADJUSTMENT', 'SALE', 'RETURN', 'RECEIPT', 'TRANSFER')),
    quantity INTEGER NOT NULL,
    previous_stock INTEGER NOT NULL,
    new_stock INTEGER NOT NULL,
    reference_id TEXT,
    reference_type TEXT,
    notes TEXT,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. SALES TRANSACTIONS & ITEMS
CREATE TABLE IF NOT EXISTS public.sales_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    receipt_number TEXT NOT NULL,
    customer_name TEXT,
    total_amount NUMERIC(12, 2) DEFAULT 0.00,
    payment_method TEXT DEFAULT 'cash',
    status TEXT DEFAULT 'completed' CHECK (status IN ('completed', 'refunded', 'cancelled')),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, receipt_number)
);

CREATE TABLE IF NOT EXISTS public.sales_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID NOT NULL REFERENCES public.sales_transactions(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. PURCHASE ORDERS & ITEMS
CREATE TABLE IF NOT EXISTS public.purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    po_number TEXT NOT NULL,
    supplier_id UUID REFERENCES public.suppliers(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'partially_received', 'received', 'cancelled')),
    total_cost NUMERIC(12, 2) DEFAULT 0.00,
    expected_delivery_date DATE,
    notes TEXT,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, po_number)
);

CREATE TABLE IF NOT EXISTS public.purchase_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_order_id UUID NOT NULL REFERENCES public.purchase_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    quantity_ordered INTEGER NOT NULL CHECK (quantity_ordered > 0),
    quantity_received INTEGER DEFAULT 0 CHECK (quantity_received >= 0),
    unit_cost NUMERIC(12, 2) NOT NULL,
    subtotal NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. INVENTORY INSIGHTS & AI RECOMMENDATIONS
CREATE TABLE IF NOT EXISTS public.inventory_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL CHECK (insight_type IN ('REORDER_NOW', 'EXPEDITE_SHIPMENT', 'HOLD_STOCK', 'OVERSTOCK', 'SLOW_MOVING', 'STOCKOUT_RISK', 'ANOMALY_DETECTED')),
    priority TEXT NOT NULL CHECK (priority IN ('CRITICAL', 'HIGH', 'NORMAL', 'LOW')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    recommended_order_qty INTEGER DEFAULT 0,
    days_of_cover NUMERIC(6, 1),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'reviewed', 'dismissed', 'actioned')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. NOTIFICATIONS
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info' CHECK (type IN ('info', 'warning', 'critical', 'success')),
    is_read BOOLEAN DEFAULT FALSE,
    link TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. ACTIVITY / AUDIT LOG
CREATE TABLE IF NOT EXISTS public.activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. INDEXES FOR HIGH QUERY PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_products_shop ON public.products(shop_id);
CREATE INDEX IF NOT EXISTS idx_products_sku ON public.products(sku);
CREATE INDEX IF NOT EXISTS idx_products_analytical ON public.products(analytical_sku_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_prod ON public.stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_shop ON public.stock_movements(shop_id);
CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON public.sales_transactions(shop_id, created_at);
CREATE INDEX IF NOT EXISTS idx_insights_shop_status ON public.inventory_insights(shop_id, status);
CREATE INDEX IF NOT EXISTS idx_po_shop ON public.purchase_orders(shop_id);

-- 14. ROW LEVEL SECURITY (RLS) POLICIES
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shops ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shop_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;

-- Helper function: Check if authenticated user belongs to shop
CREATE OR REPLACE FUNCTION public.user_has_shop_access(check_shop_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.shop_members
        WHERE shop_id = check_shop_id
          AND user_id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS POLICIES FOR SHOPS
CREATE POLICY "Users can view shops they belong to"
    ON public.shops FOR SELECT
    USING (id IN (SELECT shop_id FROM public.shop_members WHERE user_id = auth.uid()));

CREATE POLICY "Shop owners can update their shops"
    ON public.shops FOR UPDATE
    USING (owner_id = auth.uid());

CREATE POLICY "Users can create shops"
    ON public.shops FOR INSERT
    WITH CHECK (auth.uid() IS NOT NULL);

-- RLS POLICIES FOR PRODUCTS
CREATE POLICY "Users can view products of their shops"
    ON public.products FOR SELECT
    USING (public.user_has_shop_access(shop_id));

CREATE POLICY "Shop merchants can manage products"
    ON public.products FOR ALL
    USING (public.user_has_shop_access(shop_id));

-- RLS POLICIES FOR INVENTORY INSIGHTS
CREATE POLICY "Users can view shop insights"
    ON public.inventory_insights FOR SELECT
    USING (public.user_has_shop_access(shop_id));

CREATE POLICY "Shop merchants can update insights"
    ON public.inventory_insights FOR UPDATE
    USING (public.user_has_shop_access(shop_id));

-- RLS POLICIES FOR STOCK MOVEMENTS
CREATE POLICY "Users can view shop stock movements"
    ON public.stock_movements FOR SELECT
    USING (public.user_has_shop_access(shop_id));

CREATE POLICY "Users can record stock movements"
    ON public.stock_movements FOR INSERT
    WITH CHECK (public.user_has_shop_access(shop_id));

-- RLS POLICIES FOR PURCHASE ORDERS
CREATE POLICY "Users can view shop purchase orders"
    ON public.purchase_orders FOR SELECT
    USING (public.user_has_shop_access(shop_id));

CREATE POLICY "Users can manage shop purchase orders"
    ON public.purchase_orders FOR ALL
    USING (public.user_has_shop_access(shop_id));

-- RLS POLICIES FOR SALES
CREATE POLICY "Users can view shop sales"
    ON public.sales_transactions FOR SELECT
    USING (public.user_has_shop_access(shop_id));

CREATE POLICY "Users can create sales"
    ON public.sales_transactions FOR INSERT
    WITH CHECK (public.user_has_shop_access(shop_id));

-- RLS POLICIES FOR NOTIFICATIONS
CREATE POLICY "Users can view their notifications"
    ON public.notifications FOR SELECT
    USING (user_id = auth.uid() OR public.user_has_shop_access(shop_id));

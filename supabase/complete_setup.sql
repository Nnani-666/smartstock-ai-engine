-- ==============================================================================
-- SMARTSTOCK COMPLETE SUPABASE SETUP (MIGRATION + RLS + SEED DATA)
-- Target Project: txpvoqdecsjpmklelxdb
-- Dashboard SQL Editor: https://supabase.com/dashboard/project/txpvoqdecsjpmklelxdb/sql/new
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. PROFILES (Extends Supabase auth.users)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'merchant',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 2. SHOPS / STORES (Multi-shop isolation)
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 3. SHOP MEMBERS & ROLES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.shop_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'manager', 'merchant', 'staff', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, user_id)
);

-- ------------------------------------------------------------------------------
-- 4. CATEGORIES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id UUID NOT NULL REFERENCES public.shops(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (shop_id, name)
);

-- ------------------------------------------------------------------------------
-- 5. SUPPLIERS
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 6. PRODUCTS (Inventory Master)
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 7. STOCK MOVEMENTS (Auditable inventory ledger)
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 8. SALES TRANSACTIONS & ITEMS
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 9. PURCHASE ORDERS & ITEMS
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 10. INVENTORY INSIGHTS & AI RECOMMENDATIONS
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 11. NOTIFICATIONS
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 12. ACTIVITY / AUDIT LOG
-- ------------------------------------------------------------------------------
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

-- ------------------------------------------------------------------------------
-- 13. INDEXES
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_products_shop ON public.products(shop_id);
CREATE INDEX IF NOT EXISTS idx_products_sku ON public.products(sku);
CREATE INDEX IF NOT EXISTS idx_products_analytical ON public.products(analytical_sku_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_prod ON public.stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_shop ON public.stock_movements(shop_id);
CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON public.sales_transactions(shop_id, created_at);
CREATE INDEX IF NOT EXISTS idx_insights_shop_status ON public.inventory_insights(shop_id, status);
CREATE INDEX IF NOT EXISTS idx_po_shop ON public.purchase_orders(shop_id);

-- ------------------------------------------------------------------------------
-- 14. ROW LEVEL SECURITY (RLS)
-- ------------------------------------------------------------------------------
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

-- Permissive public-read for demo and authenticated access
CREATE POLICY "Public read shops" ON public.shops FOR SELECT USING (true);
CREATE POLICY "Public read products" ON public.products FOR SELECT USING (true);
CREATE POLICY "Public read categories" ON public.categories FOR SELECT USING (true);
CREATE POLICY "Public read suppliers" ON public.suppliers FOR SELECT USING (true);
CREATE POLICY "Public read insights" ON public.inventory_insights FOR SELECT USING (true);
CREATE POLICY "Public read purchase orders" ON public.purchase_orders FOR SELECT USING (true);
CREATE POLICY "Public read notifications" ON public.notifications FOR SELECT USING (true);

-- Authenticated write policies
CREATE POLICY "Auth write products" ON public.products FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Auth write stock movements" ON public.stock_movements FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Auth write purchase orders" ON public.purchase_orders FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Auth write sales" ON public.sales_transactions FOR ALL USING (auth.uid() IS NOT NULL);
CREATE POLICY "Auth write insights" ON public.inventory_insights FOR ALL USING (auth.uid() IS NOT NULL);

-- ------------------------------------------------------------------------------
-- 15. SEED DATA (The Nest General Store + Demo SKUs)
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    v_shop_id UUID;
    v_cat_pantry UUID;
    v_cat_beverage UUID;
    v_cat_home UUID;
    v_supplier_apex UUID;
    v_supplier_green UUID;
BEGIN
    SELECT id INTO v_shop_id FROM public.shops WHERE store_code = 'STORE-402';
    IF v_shop_id IS NULL THEN
        INSERT INTO public.shops (name, store_code, description, address, currency, settings)
        VALUES (
            'The Nest General Store',
            'STORE-402',
            'Boutique pantry and sustainable dry goods merchant',
            '442 Market Street, San Francisco, CA',
            'USD',
            '{"auto_reorder": false, "default_service_level": 0.98, "lead_time_days": 7}'::jsonb
        )
        RETURNING id INTO v_shop_id;
    END IF;

    -- Categories
    INSERT INTO public.categories (shop_id, name, code, description)
    VALUES 
        (v_shop_id, 'Artisan Pantry', 'PANTRY', 'Flours, grains, oats, oils, and spices'),
        (v_shop_id, 'Craft Beverages', 'BEV', 'Coffee beans, loose leaf teas, elixirs'),
        (v_shop_id, 'Eco Home & Bath', 'HOME', 'Handcrafted soaps, candles, linens')
    ON CONFLICT (shop_id, name) DO NOTHING;

    SELECT id INTO v_cat_pantry FROM public.categories WHERE shop_id = v_shop_id AND code = 'PANTRY';
    SELECT id INTO v_cat_beverage FROM public.categories WHERE shop_id = v_shop_id AND code = 'BEV';
    SELECT id INTO v_cat_home FROM public.categories WHERE shop_id = v_shop_id AND code = 'HOME';

    -- Suppliers
    INSERT INTO public.suppliers (shop_id, name, contact_name, email, phone, lead_time_days, status)
    VALUES 
        (v_shop_id, 'Apex Valley Organic Mill', 'Marcus Vance', 'orders@apexvalleymill.com', '+1 (555) 234-8901', 5, 'preferred'),
        (v_shop_id, 'Pacific Coast Roasters Co.', 'Elena Rostova', 'supply@pacificroasters.com', '+1 (555) 789-1234', 4, 'preferred'),
        (v_shop_id, 'Sonoma Heritage Organics', 'Claire Dupont', 'sales@sonomaheritage.org', '+1 (555) 456-7890', 8, 'active')
    ON CONFLICT DO NOTHING;

    SELECT id INTO v_supplier_apex FROM public.suppliers WHERE shop_id = v_shop_id AND name LIKE 'Apex%';
    SELECT id INTO v_supplier_green FROM public.suppliers WHERE shop_id = v_shop_id AND name LIKE 'Pacific%';

    -- Products
    INSERT INTO public.products (shop_id, sku, name, description, category_id, supplier_id, barcode, unit_cost, unit_price, stock_on_hand, stock_on_order, safety_stock, reorder_point, lead_time_days, status, abc_class, xyz_class, tier, analytical_sku_id)
    VALUES
        (v_shop_id, 'SKU-89240', 'Organic Rolled Oats (1kg)', 'Cold-milled organic oats, high-velocity staple', v_cat_pantry, v_supplier_apex, '079357318924', 4.50, 8.95, 24, 0, 32, 45, 5, 'low_stock', 'A', 'X', 'Strategic', 'S01-I01'),
        (v_shop_id, 'SKU-31402', 'French Dark Roast Whole Bean (12oz)', 'Direct-trade Ethiopian heirloom blend', v_cat_beverage, v_supplier_green, '079357313140', 8.20, 16.50, 14, 50, 20, 35, 4, 'low_stock', 'A', 'Y', 'Strategic', 'S01-I02'),
        (v_shop_id, 'SKU-77192', 'Artisan Cold-Pressed Olive Oil (500ml)', 'Single-estate early harvest extra virgin', v_cat_pantry, v_supplier_apex, '079357317719', 11.00, 22.00, 82, 0, 25, 40, 7, 'active', 'B', 'X', 'Strategic', 'S01-I03'),
        (v_shop_id, 'SKU-44019', 'Lavender Cedar Bar Soap (6oz)', 'Cold process tallow and essential oils', v_cat_home, NULL, '079357314401', 3.10, 7.50, 58, 0, 15, 25, 6, 'active', 'C', 'X', 'Core', 'S01-I04'),
        (v_shop_id, 'SKU-99021', 'Single Origin Matcha Powder (50g)', 'Ceremonial grade Uji green tea powder', v_cat_beverage, v_supplier_green, '079357319902', 14.50, 28.00, 3, 20, 12, 18, 5, 'low_stock', 'A', 'Z', 'Core', 'S01-I05')
    ON CONFLICT (shop_id, sku) DO NOTHING;

    -- Insights
    INSERT INTO public.inventory_insights (shop_id, product_id, insight_type, priority, title, description, recommended_order_qty, days_of_cover, status, metadata)
    SELECT 
        v_shop_id,
        p.id,
        'REORDER_NOW',
        'CRITICAL',
        'Stockout imminent on ' || p.name,
        'Current inventory (24) is below reorder point (45). Lead time demand is 28 units with 2.8 days of cover.',
        65,
        2.8,
        'active',
        '{"current_stock": 24, "reorder_point": 45, "lead_time_days": 5, "safety_stock": 32}'::jsonb
    FROM public.products p
    WHERE p.shop_id = v_shop_id AND p.sku = 'SKU-89240'
    ON CONFLICT DO NOTHING;

    INSERT INTO public.inventory_insights (shop_id, product_id, insight_type, priority, title, description, recommended_order_qty, days_of_cover, status, metadata)
    SELECT 
        v_shop_id,
        p.id,
        'EXPEDITE_SHIPMENT',
        'HIGH',
        'PO #PO-8821 in transit - Expedite requested',
        'French Dark Roast stock is down to 14 units. PO for 50 units expected in 4 days. Contact Pacific Coast Roasters.',
        0,
        1.9,
        'active',
        '{"current_stock": 14, "on_order": 50, "reorder_point": 35}'::jsonb
    FROM public.products p
    WHERE p.shop_id = v_shop_id AND p.sku = 'SKU-31402'
    ON CONFLICT DO NOTHING;

    -- Purchase Orders
    INSERT INTO public.purchase_orders (shop_id, po_number, supplier_id, status, total_cost, expected_delivery_date, notes)
    VALUES
        (v_shop_id, 'PO-8821', v_supplier_green, 'submitted', 410.00, CURRENT_DATE + INTERVAL '4 days', 'Urgent replenishment for Ethiopian French Roast')
    ON CONFLICT (shop_id, po_number) DO NOTHING;

    -- Notifications
    INSERT INTO public.notifications (shop_id, title, message, type, is_read, link)
    VALUES
        (v_shop_id, 'Stockout Alert: Organic Rolled Oats', 'Inventory at 24 units, reorder trigger reached.', 'critical', false, '/inventory'),
        (v_shop_id, 'Shipment In-Transit: PO-8821', 'Pacific Coast Roasters confirmed dispatch.', 'info', false, '/purchase-orders'),
        (v_shop_id, 'AI Weekly Demand Forecast Ready', '14-day forecasts generated for all active catalog items.', 'success', true, '/forecasts')
    ON CONFLICT DO NOTHING;

END $$;

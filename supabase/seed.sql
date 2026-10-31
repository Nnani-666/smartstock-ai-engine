-- SmartStock Seed Data
-- Shop: The Nest General Store (matching Stitch designs)

DO $$
DECLARE
    v_shop_id UUID;
    v_cat_pantry UUID;
    v_cat_beverage UUID;
    v_cat_home UUID;
    v_supplier_apex UUID;
    v_supplier_green UUID;
    v_prod_oats UUID;
    v_prod_coffee UUID;
    v_prod_oil UUID;
    v_prod_soap UUID;
BEGIN
    -- Create or fetch Shop
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

END $$;

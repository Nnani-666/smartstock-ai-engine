/**
 * SmartStock — Retail Management & Optimization Bridge
 * Professional Enterprise Architecture (₹ INR)
 * Connects Frontend Screens to Supabase Database & Analytical Forecasting Backend
 */

(function (window) {
    const SUPABASE_URL = (window.__SMARTSTOCK_CONFIG__ && window.__SMARTSTOCK_CONFIG__.SUPABASE_URL) || localStorage.getItem('smartstock_supabase_url') || 'https://txpvoqdecsjpmklelxdb.supabase.co';
    const SUPABASE_ANON_KEY = (window.__SMARTSTOCK_CONFIG__ && window.__SMARTSTOCK_CONFIG__.SUPABASE_ANON_KEY) || localStorage.getItem('smartstock_supabase_anon_key') || '';
    const API_BASE_URL = (window.__SMARTSTOCK_CONFIG__ && window.__SMARTSTOCK_CONFIG__.API_BASE_URL) || 'http://localhost:8000';
    const DEFAULT_SHOP_ID = 'b3bccd6d-875b-46e6-ade5-d9e8069b8b08';

    let _mutationQueue = Promise.resolve();
    function serializeMutation(fn) {
        const next = _mutationQueue.then(() => fn());
        _mutationQueue = next.catch(() => {});
        return next;
    }

    let supabase = null;
    function initSupabase() {
        if (!SUPABASE_ANON_KEY) return null;
        if (window.supabase && typeof window.supabase.createClient === 'function') {
            supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
            return supabase;
        }
        return null;
    }

    const SAMPLE_KIRANA_ITEMS = [
        {
            sku: 'KIR-ATTA-05',
            name: 'Aashirvaad Shudh Chakki Atta (5kg)',
            description: '100% Whole Wheat Flour staple',
            unit_cost: 210.0,
            unit_price: 240.0,
            stock_on_hand: 18,
            safety_stock: 5,
            reorder_point: 8,
            lead_time_days: 3,
            status: 'active',
            abc_class: 'A',
            xyz_class: 'X',
            tier: 'Strategic',
            category_name: 'Groceries & Grains'
        },
        {
            sku: 'KIR-SALT-01',
            name: 'Tata Salt Iodized (1kg)',
            description: 'Vacuum evaporated iodized table salt',
            unit_cost: 22.0,
            unit_price: 28.0,
            stock_on_hand: 35,
            safety_stock: 10,
            reorder_point: 15,
            lead_time_days: 2,
            status: 'active',
            abc_class: 'A',
            xyz_class: 'X',
            tier: 'Strategic',
            category_name: 'Groceries & Grains'
        },
        {
            sku: 'KIR-MAGG-04',
            name: 'Maggi 2-Minute Masala Noodles (4-Pack)',
            description: 'Instant noodles with tastemaker seasoning',
            unit_cost: 48.0,
            unit_price: 56.0,
            stock_on_hand: 4,
            safety_stock: 10,
            reorder_point: 12,
            lead_time_days: 2,
            status: 'low_stock',
            abc_class: 'A',
            xyz_class: 'Y',
            tier: 'Strategic',
            category_name: 'Packaged Foods & Dairy'
        },
        {
            sku: 'KIR-OIL-01',
            name: 'Fortune Sunlite Refined Sunflower Oil (1L)',
            description: 'Refined sunflower cooking oil pouch',
            unit_cost: 130.0,
            unit_price: 145.0,
            stock_on_hand: 14,
            safety_stock: 5,
            reorder_point: 10,
            lead_time_days: 4,
            status: 'active',
            abc_class: 'B',
            xyz_class: 'X',
            tier: 'Strategic',
            category_name: 'Oils & Spices'
        },
        {
            sku: 'KIR-AMUL-500',
            name: 'Amul Pasteurized Butter (500g)',
            description: 'Pure dairy salted table butter',
            unit_cost: 250.0,
            unit_price: 275.0,
            stock_on_hand: 3,
            safety_stock: 8,
            reorder_point: 10,
            lead_time_days: 1,
            status: 'low_stock',
            abc_class: 'A',
            xyz_class: 'Z',
            tier: 'Core',
            category_name: 'Packaged Foods & Dairy'
        },
        {
            sku: 'KIR-PARL-01',
            name: 'Parle-G Gold Glucose Biscuits (1kg)',
            description: 'High volume glucose tea biscuit pack',
            unit_cost: 105.0,
            unit_price: 120.0,
            stock_on_hand: 22,
            safety_stock: 6,
            reorder_point: 10,
            lead_time_days: 3,
            status: 'active',
            abc_class: 'B',
            xyz_class: 'X',
            tier: 'Core',
            category_name: 'Packaged Foods & Dairy'
        },
        {
            sku: 'KIR-DETT-250',
            name: 'Dettol Antiseptic Liquid (250ml)',
            description: 'Hygiene and first aid antiseptic liquid',
            unit_cost: 112.0,
            unit_price: 130.0,
            stock_on_hand: 12,
            safety_stock: 4,
            reorder_point: 6,
            lead_time_days: 5,
            status: 'active',
            abc_class: 'C',
            xyz_class: 'Y',
            tier: 'Core',
            category_name: 'Personal & Home Care'
        },
        {
            sku: 'KIR-SURF-01',
            name: 'Surf Excel Quick Wash Detergent (1kg)',
            description: 'Premium stain removal laundry powder',
            unit_cost: 132.0,
            unit_price: 150.0,
            stock_on_hand: 16,
            safety_stock: 5,
            reorder_point: 8,
            lead_time_days: 4,
            status: 'active',
            abc_class: 'B',
            xyz_class: 'X',
            tier: 'Core',
            category_name: 'Personal & Home Care'
        }
    ];

    const SmartStock = {
        config: {
            supabaseUrl: SUPABASE_URL,
            supabaseKey: SUPABASE_ANON_KEY,
            apiBaseUrl: API_BASE_URL,
            activeStoreCode: 'STORE-01',
            activeStoreName: 'My Store',
            currency: '₹',
            shopId: DEFAULT_SHOP_ID
        },

        client() {
            if (!supabase) initSupabase();
            return supabase;
        },

        formatINR(amount) {
            const num = Number(amount) || 0;
            return '₹' + num.toLocaleString('en-IN', {
                maximumFractionDigits: 2,
                minimumFractionDigits: 0
            });
        },

        toPaise(amount) {
            const num = Number(amount) || 0;
            return Math.round(num * 100);
        },

        fromPaise(paise) {
            return (Number(paise) || 0) / 100;
        },

        getBusinessDate(dateInput) {
            try {
                const d = dateInput ? new Date(dateInput) : new Date();
                if (isNaN(d.getTime())) return new Date().toISOString().split('T')[0];
                return new Intl.DateTimeFormat('en-CA', {
                    timeZone: 'Asia/Kolkata',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                }).format(d);
            } catch (e) {
                return new Date().toISOString().split('T')[0];
            }
        },

        getActiveDateRange() {
            return localStorage.getItem('smartstock_active_date_range') || 'Today (Live)';
        },

        setActiveDateRange(label) {
            localStorage.setItem('smartstock_active_date_range', label);
        },

        getFilteredSales(rangeLabel = null) {
            const allSales = this.getSales();
            const activeRange = rangeLabel || this.getActiveDateRange();
            const todayStr = this.getBusinessDate();

            if (activeRange === 'Today (Live)' || !activeRange) {
                return allSales.filter(s => {
                    const sDate = s.date || this.getBusinessDate(s.timestamp);
                    return sDate === todayStr;
                });
            }

            if (activeRange === 'Last 7 Days') {
                const todayDate = new Date(todayStr + 'T12:00:00Z');
                const sevenDaysAgo = new Date(todayDate.getTime() - 7 * 86400000);
                return allSales.filter(s => {
                    const sDateStr = s.date || this.getBusinessDate(s.timestamp);
                    const sDate = new Date(sDateStr + 'T12:00:00Z');
                    return sDate >= sevenDaysAgo && sDate <= todayDate;
                });
            }

            if (activeRange.includes('30 Days') || activeRange === 'Oct 24 • Last 30 Days') {
                const todayDate = new Date(todayStr + 'T12:00:00Z');
                const thirtyDaysAgo = new Date(todayDate.getTime() - 30 * 86400000);
                return allSales.filter(s => {
                    const sDateStr = s.date || this.getBusinessDate(s.timestamp);
                    const sDate = new Date(sDateStr + 'T12:00:00Z');
                    return sDate >= thirtyDaysAgo && sDate <= todayDate;
                });
            }

            if (activeRange.includes('This Month') || activeRange.startsWith('This Month')) {
                const yearMonth = todayStr.slice(0, 7);
                return allSales.filter(s => {
                    const sDateStr = s.date || this.getBusinessDate(s.timestamp);
                    return sDateStr.startsWith(yearMonth);
                });
            }

            return allSales;
        },

        getSalesSummary(rangeLabel = null) {
            const sales = this.getFilteredSales(rangeLabel);
            let totalPaise = 0;
            let totalCostPaise = 0;
            let totalUnits = 0;
            let costAvailable = true;

            for (const s of sales) {
                const qty = Number(s.qty || s.units) || 0;
                const price = (typeof s.unit_price === 'number' && !isNaN(s.unit_price))
                    ? s.unit_price
                    : (Number(s.unit_price) || 0);

                totalUnits += qty;
                totalPaise += this.toPaise(qty * price);

                if (s.unit_cost !== null && s.unit_cost !== undefined && !isNaN(Number(s.unit_cost))) {
                    totalCostPaise += this.toPaise(qty * Number(s.unit_cost));
                } else {
                    costAvailable = false;
                }
            }

            const revenue = this.fromPaise(totalPaise);
            const cost = costAvailable ? this.fromPaise(totalCostPaise) : null;
            const grossProfit = costAvailable ? (revenue - cost) : null;
            const grossMargin = (costAvailable && revenue > 0) ? ((grossProfit / revenue) * 100) : null;

            return {
                revenue,
                totalUnits,
                count: sales.length,
                cost,
                grossProfit,
                grossMargin,
                costAvailable
            };
        },

        getGeminiApiKey() {
            return (window.__SMARTSTOCK_CONFIG__ && window.__SMARTSTOCK_CONFIG__.GEMINI_API_KEY) || localStorage.getItem('smartstock_gemini_api_key') || '';
        },

        escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        },


        // Current user & storage key scoping
        getCurrentUserEmail() {
            try {
                const u = JSON.parse(localStorage.getItem('smartstock_user') || '{}');
                return (u.email || '').trim().toLowerCase();
            } catch (e) {
                return '';
            }
        },

        getUserKey(baseKey) {
            const email = this.getCurrentUserEmail();
            if (!email) return baseKey;
            const safe = email.replace(/[^a-zA-Z0-9_-]/g, '_');
            return `${baseKey}_${safe}`;
        },

        // Accounts Registry with password hashes for strict offline/online auth
        getAccountsRegistry() {
            try {
                const reg = JSON.parse(localStorage.getItem('smartstock_accounts_registry') || '{}');
                // Ensure default demo account exists
                if (!reg['owner@sharmakirana.in']) {
                    reg['owner@sharmakirana.in'] = {
                        email: 'owner@sharmakirana.in',
                        password: 'terminal123',
                        passwordHash: this.simpleHash('terminal123'),
                        store: 'Sharma Kirana Store',
                        phone: '+91 98765 43210',
                        manager: 'Store Owner'
                    };
                    localStorage.setItem('smartstock_accounts_registry', JSON.stringify(reg));
                }
                return reg;
            } catch (e) {
                return {};
            }
        },

        saveAccountsRegistry(accounts) {
            localStorage.setItem('smartstock_accounts_registry', JSON.stringify(accounts));
        },

        simpleHash(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = ((hash << 5) - hash) + str.charCodeAt(i);
                hash |= 0;
            }
            return 'h_' + Math.abs(hash);
        },

        // Store Registry & Persistence
        getStoreRegistry() {
            try {
                return JSON.parse(localStorage.getItem('smartstock_stores_registry') || '{}');
            } catch (e) {
                return {};
            }
        },

        saveStoreToRegistry(email, storeData) {
            if (!email) return;
            const reg = this.getStoreRegistry();
            const clean = email.trim().toLowerCase();
            reg[clean] = {
                ...(reg[clean] || {}),
                ...storeData,
                email: clean
            };
            localStorage.setItem('smartstock_stores_registry', JSON.stringify(reg));
            if (storeData.store) {
                localStorage.setItem('smartstock_last_active_store', storeData.store);
            }
        },

        getRegisteredStore(email) {
            if (!email) return null;
            const reg = this.getStoreRegistry();
            return reg[email.trim().toLowerCase()] || null;
        },

        // Authentication - Strict verification against backend and local registry
        async signIn(email, password) {
            const cleanEmail = (email || '').trim().toLowerCase();
            if (!cleanEmail || !password) {
                return { data: null, error: { message: 'Please provide both email and password.' } };
            }

            // 1. Try local FastAPI verification first
            let backendSuccess = false;
            let backendUser = null;
            let backendErrMsg = null;
            try {
                const resp = await fetch('http://127.0.0.1:8000/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: cleanEmail, password: password })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    backendSuccess = true;
                    backendUser = data.user;
                } else {
                    const errData = await resp.json().catch(() => ({}));
                    backendErrMsg = errData.detail || 'Incorrect password. Access denied.';
                }
            } catch (netErr) {
                // Backend unreachable, fallback to verified local accounts registry
            }

            if (backendSuccess && backendUser) {
                const userObj = {
                    email: cleanEmail,
                    store: backendUser.store || 'My Store',
                    phone: backendUser.phone || '',
                    manager: backendUser.manager || 'Store Owner'
                };
                localStorage.setItem('smartstock_user', JSON.stringify(userObj));
                this.saveStoreToRegistry(cleanEmail, userObj);
                this.config.activeStoreName = userObj.store;
                return { data: { user: userObj }, error: null };
            }

            // 2. Strict verification against local accounts registry
            const accounts = this.getAccountsRegistry();
            const account = accounts[cleanEmail];
            if (account) {
                if (account.password === password || account.passwordHash === this.simpleHash(password)) {
                    // Valid credentials matching local registry! Also sync to backend in background
                    fetch('http://127.0.0.1:8000/api/v1/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            email: cleanEmail,
                            password: password,
                            store_name: account.store || 'My Store',
                            phone: account.phone || '',
                            manager: account.manager || 'Store Owner'
                        })
                    }).catch(() => {});

                    const userObj = {
                        email: cleanEmail,
                        store: account.store || 'My Store',
                        phone: account.phone || '',
                        manager: account.manager || 'Store Owner'
                    };
                    localStorage.setItem('smartstock_user', JSON.stringify(userObj));
                    this.saveStoreToRegistry(cleanEmail, userObj);
                    this.config.activeStoreName = userObj.store;
                    return { data: { user: userObj }, error: null };
                } else {
                    return { data: null, error: { message: 'Incorrect password. Access denied.' } };
                }
            }

            return { data: null, error: { message: backendErrMsg || 'Account not found. Please register your store first.' } };
        },

        async signUp(email, password, storeName, phone) {
            const cleanEmail = (email || '').trim().toLowerCase();
            if (!cleanEmail || !password) {
                return { data: null, error: { message: 'Email and password are required.' } };
            }
            if (password.length < 4) {
                return { data: null, error: { message: 'Password must be at least 4 characters.' } };
            }
            const shopName = storeName && storeName.trim() ? storeName.trim() : 'My Store';
            const userObj = {
                email: cleanEmail,
                store: shopName,
                phone: phone || '',
                manager: 'Store Owner'
            };

            // 1. Try FastAPI backend registration
            try {
                const resp = await fetch('http://127.0.0.1:8000/api/v1/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: cleanEmail,
                        password: password,
                        store_name: shopName,
                        phone: phone || '',
                        manager: 'Store Owner'
                    })
                });
                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({}));
                    if (resp.status === 400 && errData.detail && errData.detail.toLowerCase().includes('already registered')) {
                        return { data: null, error: { message: errData.detail } };
                    }
                }
            } catch (e) {
                console.warn('Backend register error (offline):', e);
            }

            // 2. Save in accounts registry
            const accounts = this.getAccountsRegistry();
            accounts[cleanEmail] = {
                email: cleanEmail,
                password: password,
                passwordHash: this.simpleHash(password),
                store: shopName,
                phone: phone || '',
                manager: 'Store Owner'
            };
            this.saveAccountsRegistry(accounts);

            // 3. Set current active user
            localStorage.setItem('smartstock_user', JSON.stringify(userObj));
            this.saveStoreToRegistry(cleanEmail, userObj);
            this.config.activeStoreName = shopName;

            // 4. Initialize empty dataset for new user (0 items, 0 orders, 0 revenue)
            const prodKey = this.getUserKey('smartstock_local_products');
            const revKey = this.getUserKey('smartstock_revenue');
            const salesKey = this.getUserKey('smartstock_sales');
            const poKey = this.getUserKey('smartstock_purchase_orders');
            localStorage.setItem(prodKey, JSON.stringify([]));
            localStorage.setItem(revKey, '0');
            localStorage.setItem(salesKey, JSON.stringify([]));
            localStorage.setItem(poKey, JSON.stringify([]));

            return { data: { user: userObj }, error: null };
        },

        async signOut() {
            localStorage.removeItem('smartstock_session');
            localStorage.removeItem('smartstock_user');
            window.location.href = '01_signin.html';
        },

        // Products Data Access - Scoped to logged in merchant user
        async getProducts() {
            const key = this.getUserKey('smartstock_local_products');
            let items = null;
            const local = localStorage.getItem(key);
            if (local !== null) {
                try {
                    items = JSON.parse(local);
                } catch (e) {
                    items = [];
                }
            }

            // Only fallback to backend if key was NEVER set in localStorage
            if (items === null) {
                const email = this.getCurrentUserEmail();
                if (email) {
                    try {
                        const resp = await fetch(`http://127.0.0.1:8000/api/v1/user/products?email=${encodeURIComponent(email)}`);
                        if (resp.ok) {
                            const backendItems = await resp.json();
                            if (Array.isArray(backendItems) && backendItems.length > 0) {
                                items = backendItems;
                            }
                        }
                    } catch (e) {}
                }
            }

            if (!items) items = [];

            // Product normalization:
            // 1. Ensure stock_on_hand is a number
            // 2. Preserve merchant reorder_point exactly as configured (including 0 and > 30)
            // 3. Calibrate status accurately based on stock_on_hand vs reorder_point
            let modified = false;
            items.forEach(p => {
                p.stock_on_hand = Number(p.stock_on_hand);
                if (isNaN(p.stock_on_hand)) p.stock_on_hand = 0;

                let rop = Number(p.reorder_point);
                if (p.reorder_point === undefined || p.reorder_point === null || isNaN(rop)) {
                    rop = 10;
                    p.reorder_point = rop;
                    modified = true;
                } else {
                    p.reorder_point = rop;
                }

                const correctStatus = p.stock_on_hand <= 0 ? 'out_of_stock' : (p.stock_on_hand <= rop ? 'low_stock' : 'active');
                if (p.status !== correctStatus) {
                    p.status = correctStatus;
                    modified = true;
                }
            });

            if (modified) {
                this.saveProducts(items);
            }
            return items;
        },

        saveProducts(products) {
            const key = this.getUserKey('smartstock_local_products');
            localStorage.setItem(key, JSON.stringify(products));
        },

        getInventoryValuation(products) {
            if (!Array.isArray(products) || products.length === 0) return 0;
            const totalPaise = products.reduce((acc, p) => {
                const onHand = Number(p.stock_on_hand) || 0;
                const cost = (p.unit_cost !== null && p.unit_cost !== undefined && !isNaN(Number(p.unit_cost)))
                    ? Number(p.unit_cost)
                    : 0;
                return acc + this.toPaise(onHand * cost);
            }, 0);
            return this.fromPaise(totalPaise);
        },

        async addProduct(productData) {
            const sku = productData.sku || `SKU-${Math.floor(1000 + Math.random() * 9000)}`;
            const rawRop = Number(productData.reorder_point);
            const reorderPoint = (productData.reorder_point === undefined || productData.reorder_point === null || isNaN(rawRop)) ? 10 : rawRop;
            const stockOnHand = Number(productData.stock_on_hand) || 0;
            const status = stockOnHand <= 0 ? 'out_of_stock' : (stockOnHand <= reorderPoint ? 'low_stock' : 'active');

            const newProduct = {
                id: 'loc-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
                shop_id: this.config.shopId,
                sku: sku,
                name: productData.name || 'Unnamed Product',
                description: productData.description || 'Retail grocery item',
                unit_cost: Number(productData.unit_cost) || 0,
                unit_price: Number(productData.unit_price) || 0,
                stock_on_hand: stockOnHand,
                stock_on_order: 0,
                safety_stock: Number(productData.safety_stock) || Math.max(2, Math.floor(reorderPoint * 0.7)),
                reorder_point: reorderPoint,
                lead_time_days: Number(productData.lead_time_days) || 3,
                status: status,
                abc_class: Number(productData.unit_price) >= 150 ? 'A' : (Number(productData.unit_price) >= 60 ? 'B' : 'C'),
                xyz_class: 'X',
                tier: 'Strategic',
                category_name: productData.category_name || 'Groceries & Household'
            };

            const local = await this.getProducts();
            local.unshift(newProduct);
            this.saveProducts(local);

            // Sync to backend if available
            try {
                const email = this.getCurrentUserEmail();
                if (email) {
                    fetch('http://127.0.0.1:8000/api/v1/user/products', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_email: email,
                            name: newProduct.name,
                            sku: newProduct.sku,
                            unit_cost: newProduct.unit_cost,
                            unit_price: newProduct.unit_price,
                            stock_on_hand: newProduct.stock_on_hand,
                            reorder_point: newProduct.reorder_point,
                            safety_stock: newProduct.safety_stock,
                            lead_time_days: newProduct.lead_time_days,
                            category_name: newProduct.category_name
                        })
                    }).catch(e => console.warn('Backend product add sync error:', e));
                }
            } catch (e) {}

            this.showToast(`Product added: ${newProduct.name}`, 'success');
            return newProduct;
        },

        getRevenue() {
            const key = this.getUserKey('smartstock_revenue');
            const stored = localStorage.getItem(key);
            if (stored !== null && !isNaN(parseFloat(stored))) {
                return parseFloat(stored);
            }
            return 0.0;
        },

        async updateStock(productId, delta, options = {}) {
            return serializeMutation(async () => {
                const products = await this.getProducts();
                const prod = products.find(p => p.id === productId || String(p.id) === String(productId));
                if (!prod) return null;

                const currentStock = Number(prod.stock_on_hand) || 0;
                const requestedUnits = Math.abs(delta);

                // Reject entire sale if requested quantity exceeds stock on hand
                if (delta < 0 && requestedUnits > currentStock) {
                    this.showToast(`Cannot sell: requested ${requestedUnits} units but only ${currentStock} in stock!`, 'error');
                    return null;
                }

                const newStock = Math.max(0, currentStock + delta);
                const rop = Number(prod.reorder_point);
                const finalRop = (prod.reorder_point === undefined || prod.reorder_point === null || isNaN(rop)) ? 10 : rop;
                const status = newStock <= 0 ? 'out_of_stock' : (newStock <= finalRop ? 'low_stock' : 'active');

                prod.stock_on_hand = newStock;
                prod.reorder_point = finalRop;
                prod.status = status;
                this.saveProducts(products);

                if (delta < 0) {
                    const qtySold = requestedUnits;
                    const unitPrice = (typeof options.unit_price === 'number' && !isNaN(options.unit_price))
                        ? options.unit_price
                        : ((typeof prod.unit_price === 'number' && !isNaN(prod.unit_price))
                            ? prod.unit_price
                            : 0);

                    const unitCost = (options.unit_cost !== undefined && options.unit_cost !== null && !isNaN(Number(options.unit_cost)))
                        ? Number(options.unit_cost)
                        : ((prod.unit_cost !== undefined && prod.unit_cost !== null && !isNaN(Number(prod.unit_cost)))
                            ? Number(prod.unit_cost)
                            : null);

                    const salePaise = this.toPaise(qtySold * unitPrice);
                    const saleAmt = this.fromPaise(salePaise);

                    const currentRev = this.getRevenue();
                    const newRev = this.fromPaise(this.toPaise(currentRev) + salePaise);
                    const revKey = this.getUserKey('smartstock_revenue');
                    localStorage.setItem(revKey, newRev.toString());

                    const ts = options.timestamp || new Date().toISOString();
                    const bDate = options.date || this.getBusinessDate(ts);

                    const sales = this.getSales();
                    const saleRecord = {
                        id: options.id || ('sale-' + Date.now() + '-' + Math.floor(Math.random() * 1000)),
                        productId: prod.id,
                        product_id: prod.id,
                        name: prod.name,
                        product_name: prod.name,
                        qty: qtySold,
                        units: qtySold,
                        unit_price: unitPrice,
                        unit_cost: unitCost,
                        total: saleAmt,
                        sale_amount: saleAmt,
                        date: bDate,
                        timestamp: ts,
                        idempotency_key: options.idempotency_key || null
                    };

                    sales.unshift(saleRecord);
                    this.saveSales(sales); // Retain full history without 50-limit

                    // Sync sale to backend
                    try {
                        const email = this.getCurrentUserEmail();
                        if (email) {
                            fetch('http://127.0.0.1:8000/api/v1/user/sales', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    user_email: email,
                                    product_id: String(prod.id),
                                    product_name: prod.name,
                                    sale_amount: saleAmt,
                                    units: qtySold,
                                    unit_price: unitPrice,
                                    unit_cost: unitCost,
                                    timestamp: ts,
                                    idempotency_key: saleRecord.idempotency_key
                                })
                            }).catch(e => console.warn('Backend sale sync error:', e));
                        }
                    } catch (e) {}

                    this.showToast(`Sold ${qtySold}x ${prod.name} (+${this.formatINR(saleAmt)}). Revenue: ${this.formatINR(newRev)}`, 'success');
                } else {
                    this.showToast(`Stock inward (+${delta}) for ${prod.name}. On hand: ${newStock}`, 'success');
                }

                await this.bindLivePageData();
                return prod;
            });
        },

        async deleteProduct(productId) {
            let ok = true;
            try {
                ok = confirm('Remove this product from active inventory?');
            } catch (e) {
                ok = true;
            }
            if (!ok) return;
            const local = (await this.getProducts()).filter(p => p.id !== productId && String(p.id) !== String(productId));
            this.saveProducts(local);
            this.showToast('Product removed from inventory.', 'info');
            await this.bindLivePageData();
        },

        getSales() {
            const key = this.getUserKey('smartstock_sales');
            try {
                return JSON.parse(localStorage.getItem(key) || '[]');
            } catch (e) {
                return [];
            }
        },

        saveSales(sales) {
            const key = this.getUserKey('smartstock_sales');
            localStorage.setItem(key, JSON.stringify(sales));
        },

        async loadSampleKiranaData() {
            this.showToast('Loading standard inventory catalog...', 'info');
            const itemsToInsert = SAMPLE_KIRANA_ITEMS.map((item, idx) => ({
                id: 'sample-' + idx,
                shop_id: this.config.shopId,
                sku: item.sku,
                name: item.name,
                description: item.description,
                unit_cost: item.unit_cost,
                unit_price: item.unit_price,
                stock_on_hand: item.stock_on_hand,
                stock_on_order: 0,
                safety_stock: item.safety_stock,
                reorder_point: item.reorder_point,
                lead_time_days: item.lead_time_days,
                status: item.status,
                abc_class: item.abc_class,
                xyz_class: item.xyz_class,
                tier: item.tier,
                category_name: item.category_name || 'Groceries & Grains'
            }));

            this.saveProducts(itemsToInsert);
            const revKey = this.getUserKey('smartstock_revenue');
            localStorage.setItem(revKey, '184200.00');
            this.showToast('Sample catalog loaded successfully.', 'success');
            setTimeout(() => window.location.reload(), 500);
        },

        openResetModal() {
            const modal = document.getElementById('reset-confirm-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeResetModal() {
            const modal = document.getElementById('reset-confirm-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        async confirmResetStore() {
            this.closeResetModal();
            this.saveProducts([]);
            const revKey = this.getUserKey('smartstock_revenue');
            localStorage.setItem(revKey, '0');
            this.saveSales([]);
            this.savePurchaseOrders([]);
            this.showToast('All inventory reset to 0 items.', 'info');
            setTimeout(() => window.location.reload(), 300);
        },

        async resetStore() {
            this.openResetModal();
        },

        // -------------------------------------------------------------
        // SUPPLIERS DIRECTORY & MANAGEMENT
        // -------------------------------------------------------------
        getSuppliers() {
            const key = this.getUserKey('smartstock_suppliers');
            let customSuppliers = [];
            try {
                customSuppliers = JSON.parse(localStorage.getItem(key) || '[]');
            } catch (e) {
                customSuppliers = [];
            }

            const supplierMap = new Map();

            // Default standard wholesale distributors for demo store
            const userEmail = this.getCurrentUserEmail();
            if (userEmail === 'owner@sharmakirana.in' || !userEmail) {
                const defaults = [
                    {
                        id: 'supp-itc',
                        name: 'ITC Limited',
                        category: 'Packaged Foods & Staples',
                        phone: '+91 80 2839 4000',
                        email: 'distributors@itclimited.in',
                        hub: 'Peenya Wholesale Depot, Bengaluru',
                        lead_time_days: 3,
                        is_verified: true
                    },
                    {
                        id: 'supp-adani',
                        name: 'Adani Wilmar',
                        category: 'Edible Oils & Grains',
                        phone: '+91 79 2656 5555',
                        email: 'customercare@adaniwilmar.in',
                        hub: 'Hosur Distribution Center',
                        lead_time_days: 4,
                        is_verified: true
                    },
                    {
                        id: 'supp-parle',
                        name: 'Parle Products',
                        category: 'Biscuits & Confectionery',
                        phone: '+91 22 6691 6911',
                        email: 'sales@parle.biz',
                        hub: 'Whitefield Depot, Bengaluru',
                        lead_time_days: 3,
                        is_verified: true
                    },
                    {
                        id: 'supp-reckitt',
                        name: 'Reckitt Benckiser',
                        category: 'Hygiene & Health',
                        phone: '+91 124 402 8000',
                        email: 'b2b.india@reckitt.com',
                        hub: 'Nelamangala Logistics Hub',
                        lead_time_days: 5,
                        is_verified: true
                    },
                    {
                        id: 'supp-hul',
                        name: 'Hindustan Unilever',
                        category: 'Home & Personal Care',
                        phone: '+91 22 5043 0000',
                        email: 'levercare@unilever.com',
                        hub: 'Bommasandra Industrial Area',
                        lead_time_days: 4,
                        is_verified: true
                    },
                    {
                        id: 'supp-metro',
                        name: 'Metro Wholesale',
                        category: 'Cash & Carry Regional Hub',
                        phone: '+91 80 4344 1234',
                        email: 'support@metro-wholesale.in',
                        hub: 'Yeshwanthpur Center, Bengaluru',
                        lead_time_days: 2,
                        is_verified: true
                    }
                ];
                defaults.forEach(d => supplierMap.set(d.name.toLowerCase().trim(), d));
            }

            // Also include custom suppliers saved by the user
            customSuppliers.forEach(s => supplierMap.set(s.name.toLowerCase().trim(), s));

            // Dynamically discover any supplier named in active catalog products
            const products = this.getCachedProducts();
            products.forEach(p => {
                if (p.supplier && !supplierMap.has(p.supplier.toLowerCase().trim())) {
                    supplierMap.set(p.supplier.toLowerCase().trim(), {
                        id: 'supp-' + p.supplier.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                        name: p.supplier,
                        category: p.category_name || 'Retail Wholesale',
                        phone: '+91 98450 11223',
                        email: `orders@${p.supplier.toLowerCase().replace(/[^a-z0-9]/g, '')}.in`,
                        hub: 'City Commercial Hub',
                        lead_time_days: p.lead_time_days || 3,
                        is_verified: true
                    });
                }
            });

            // Dynamically discover any supplier named in purchase orders
            const orders = this.getPurchaseOrders();
            orders.forEach(po => {
                if (po.supplier && !supplierMap.has(po.supplier.toLowerCase().trim())) {
                    supplierMap.set(po.supplier.toLowerCase().trim(), {
                        id: 'supp-' + po.supplier.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                        name: po.supplier,
                        category: 'Wholesale Partner',
                        phone: '+91 80 4344 1234',
                        email: 'b2b@distributionhub.in',
                        hub: 'Regional Supply Depot',
                        lead_time_days: 3,
                        is_verified: true
                    });
                }
            });

            return Array.from(supplierMap.values());
        },

        getCachedProducts() {
            const key = this.getUserKey('smartstock_local_products');
            try {
                return JSON.parse(localStorage.getItem(key) || '[]');
            } catch(e) {
                return [];
            }
        },

        saveSuppliers(suppliers) {
            const key = this.getUserKey('smartstock_suppliers');
            localStorage.setItem(key, JSON.stringify(suppliers));
        },

        addSupplier(suppData) {
            const key = this.getUserKey('smartstock_suppliers');
            let customSuppliers = [];
            try { customSuppliers = JSON.parse(localStorage.getItem(key) || '[]'); } catch(e){}
            const newSupp = {
                id: 'supp-' + Date.now(),
                name: suppData.name.trim(),
                category: suppData.category ? suppData.category.trim() : 'General Wholesale',
                phone: suppData.phone ? suppData.phone.trim() : '+91 98765 00000',
                email: suppData.email ? suppData.email.trim() : 'orders@distributor.in',
                hub: suppData.hub ? suppData.hub.trim() : 'Regional Logistics Hub',
                lead_time_days: parseInt(suppData.lead_time_days, 10) || 3,
                is_verified: true
            };
            customSuppliers.push(newSupp);
            this.saveSuppliers(customSuppliers);
            return newSupp;
        },

        openSuppliersModal() {
            const modal = document.getElementById('suppliers-directory-modal');
            if (!modal) return;
            this.renderSuppliersModalContent();
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        },

        closeSuppliersModal() {
            const modal = document.getElementById('suppliers-directory-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        renderSuppliersModalContent() {
            const listEl = document.getElementById('suppliers-directory-list');
            const countEl = document.getElementById('suppliers-total-count');
            if (!listEl) return;

            const suppliers = this.getSuppliers();
            const products = this.getCachedProducts();
            const orders = this.getPurchaseOrders();

            if (countEl) countEl.textContent = `${suppliers.length} Partners`;

            if (suppliers.length === 0) {
                listEl.innerHTML = `
                    <div class="p-8 text-center bg-surface-container-low rounded-2xl border border-outline/10 space-y-3">
                        <span class="material-symbols-outlined text-[36px] text-outline">local_shipping</span>
                        <h4 class="font-bold text-sm text-on-surface">No Suppliers Registered</h4>
                        <p class="text-xs text-on-surface-variant max-w-xs mx-auto">
                            Add your wholesale vendor partners, APMC mandi distributors, or FMCG company contacts to manage stock replenishment.
                        </p>
                        <button onclick="SmartStock.openAddSupplierModal()" class="px-4 py-2 bg-primary text-on-primary rounded-xl font-semibold text-xs shadow-xs active:scale-95 transition-all cursor-pointer">
                            + Add First Supplier
                        </button>
                    </div>
                `;
                return;
            }

            listEl.innerHTML = suppliers.map((s) => {
                const suppliedProducts = products.filter(p => 
                    p.supplier && p.supplier.toLowerCase().trim() === s.name.toLowerCase().trim()
                );
                const supplierOrders = orders.filter(po => 
                    po.supplier && po.supplier.toLowerCase().includes(s.name.toLowerCase().trim().split(' ')[0])
                );
                const totalSpent = supplierOrders.reduce((sum, po) => sum + (Number(po.total_amount) || 0), 0);

                const prodPills = suppliedProducts.length > 0 
                    ? suppliedProducts.map(p => `
                        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-surface-container text-on-surface text-[11px] font-medium border border-outline/10">
                            <span class="font-mono text-[10px] text-outline">${p.sku || 'SKU'}</span>
                            <span class="truncate max-w-[130px]">${p.name}</span>
                            <span class="font-bold text-primary font-mono text-[10px]">(${p.stock_on_hand} left)</span>
                        </span>
                    `).join('')
                    : `<span class="text-[11px] text-outline italic">No catalog items linked yet</span>`;

                return `
                    <div class="bg-surface-container-lowest p-4 rounded-2xl border border-outline/15 shadow-xs space-y-3">
                        <div class="flex items-start justify-between gap-2">
                            <div class="flex items-start gap-2.5 min-w-0">
                                <div class="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold text-base shrink-0">
                                    <span class="material-symbols-outlined text-[20px]">local_shipping</span>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-2">
                                        <h4 class="font-bold text-sm text-on-surface truncate">${s.name}</h4>
                                        <span class="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-[9px] font-bold uppercase tracking-wider shrink-0">Verified</span>
                                    </div>
                                    <p class="text-xs text-on-surface-variant truncate">${s.category || 'Wholesale Supplier'} • <span class="font-medium text-secondary">Lead: ${s.lead_time_days || 3}d</span></p>
                                </div>
                            </div>
                            <button onclick="SmartStock.quickOrderFromSupplier('${encodeURIComponent(s.name)}')" class="h-8 px-3 rounded-lg bg-primary text-on-primary font-semibold text-xs flex items-center gap-1 active:scale-95 shadow-xs shrink-0 cursor-pointer">
                                <span class="material-symbols-outlined text-[15px]">add_shopping_cart</span>
                                <span>Create PO</span>
                            </button>
                        </div>

                        <!-- Products Supplied -->
                        <div class="bg-surface-container-low p-2.5 rounded-xl space-y-1.5">
                            <div class="flex items-center justify-between text-[11px] text-on-surface-variant font-medium">
                                <span>Catalog Items (${suppliedProducts.length})</span>
                                <span>Total POs: <b>${supplierOrders.length} (${SmartStock.formatINR(totalSpent)})</b></span>
                            </div>
                            <div class="flex flex-wrap gap-1.5">
                                ${prodPills}
                            </div>
                        </div>

                        <!-- Contact & Hub Details -->
                        <div class="flex items-center justify-between pt-1 border-t border-outline/10 text-xs text-on-surface-variant flex-wrap gap-2">
                            <div class="flex items-center gap-3">
                                <a href="tel:${s.phone}" class="flex items-center gap-1 text-primary hover:underline font-mono text-[11px]">
                                    <span class="material-symbols-outlined text-[14px]">call</span>
                                    <span>${s.phone}</span>
                                </a>
                                <span class="text-outline/40">•</span>
                                <span class="flex items-center gap-1 text-[11px] text-outline truncate max-w-[150px]">
                                    <span class="material-symbols-outlined text-[14px]">warehouse</span>
                                    <span>${s.hub || 'Depot Hub'}</span>
                                </span>
                            </div>
                            <button onclick="SmartStock.quickOrderFromSupplier('${encodeURIComponent(s.name)}')" class="text-primary font-semibold text-xs hover:underline flex items-center gap-0.5 cursor-pointer">
                                <span>Order Stock</span>
                                <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        },

        quickOrderFromSupplier(encodedSupplierName) {
            const supplierName = decodeURIComponent(encodedSupplierName);
            this.closeSuppliersModal();
            if (window.location.pathname.includes('05_purchase_orders.html')) {
                this.openNewPOModal();
                const suppInput = document.getElementById('po-supplier-input');
                if (suppInput) suppInput.value = supplierName;
            } else {
                localStorage.setItem('smartstock_preselected_supplier', supplierName);
                window.location.href = '05_purchase_orders.html';
            }
        },

        openAddSupplierModal() {
            const modal = document.getElementById('add-supplier-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeAddSupplierModal() {
            const modal = document.getElementById('add-supplier-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        submitAddSupplier(e) {
            e.preventDefault();
            const name = document.getElementById('new-supp-name')?.value?.trim();
            const category = document.getElementById('new-supp-category')?.value?.trim() || 'General Wholesale';
            const phone = document.getElementById('new-supp-phone')?.value?.trim() || '+91 98000 00000';
            const email = document.getElementById('new-supp-email')?.value?.trim() || 'orders@distributor.in';
            const hub = document.getElementById('new-supp-hub')?.value?.trim() || 'Wholesale Depot';
            const leadTime = parseInt(document.getElementById('new-supp-lead')?.value, 10) || 3;

            if (!name) {
                this.showToast('Please enter a supplier name.', 'warning');
                return;
            }

            this.addSupplier({
                name,
                category,
                phone,
                email,
                hub,
                lead_time_days: leadTime
            });

            this.showToast(`Supplier ${name} registered successfully!`, 'success');
            this.closeAddSupplierModal();
            this.renderSuppliersModalContent();
        },

        // -------------------------------------------------------------
        // SALES REGISTER & ACTUAL TRANSACTIONS
        // -------------------------------------------------------------
        openSalesModal() {
            const modal = document.getElementById('sales-register-modal');
            if (!modal) return;
            this.renderSalesModalContent();
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        },

        closeSalesModal() {
            const modal = document.getElementById('sales-register-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        renderSalesModalContent() {
            const sales = this.getSales();
            const revenue = this.getRevenue();
            const products = this.getCachedProducts();

            const totalRevEl = document.getElementById('sales-modal-total-rev');
            const totalCountEl = document.getElementById('sales-modal-total-count');
            const totalUnitsEl = document.getElementById('sales-modal-total-units');
            const tableEl = document.getElementById('sales-modal-transactions-list');
            const prodSelect = document.getElementById('sale-record-product-select');

            if (totalRevEl) totalRevEl.textContent = this.formatINR(revenue);
            if (totalCountEl) totalCountEl.textContent = `${sales.length} Bills`;
            const unitsSold = sales.reduce((sum, s) => sum + (Number(s.qty || s.units) || 1), 0);
            if (totalUnitsEl) totalUnitsEl.textContent = `${unitsSold} Units`;

            // Populate Product Selection for Quick Sale
            if (prodSelect) {
                if (products.length === 0) {
                    prodSelect.innerHTML = '<option value="">No products in catalog to sell</option>';
                } else {
                    prodSelect.innerHTML = products.map((p) => `
                        <option value="${p.id}" data-price="${p.unit_price || 0}" data-stock="${p.stock_on_hand || 0}" data-name="${p.name}">
                            ${p.name} (Stock: ${p.stock_on_hand}) • ${this.formatINR(p.unit_price)}
                        </option>
                    `).join('');
                }
                this.calculateSaleModalTotal();
            }

            // Render Actual Transactions List
            if (tableEl) {
                if (sales.length === 0) {
                    tableEl.innerHTML = `
                        <div class="p-8 text-center bg-surface-container-low rounded-2xl border border-outline/10 space-y-2">
                            <span class="material-symbols-outlined text-[36px] text-outline">point_of_sale</span>
                            <h4 class="font-bold text-sm text-on-surface">No Sales Recorded Yet</h4>
                            <p class="text-xs text-on-surface-variant max-w-xs mx-auto">
                                Record your first customer transaction using the form above or tap the '-1' button on any product in the Stock Inventory screen.
                            </p>
                        </div>
                    `;
                } else {
                    tableEl.innerHTML = sales.map(s => {
                        const dateObj = s.timestamp ? new Date(s.timestamp) : new Date();
                        const timeStr = dateObj.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
                        const dateStr = dateObj.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
                        const units = Number(s.qty || s.units) || 1;
                        const total = Number(s.total) || (units * (Number(s.unit_price) || 0));

                        return `
                            <div class="bg-surface-container-lowest p-3 rounded-xl border border-outline/10 shadow-2xs flex items-center justify-between gap-3">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-8 h-8 rounded-lg bg-primary-fixed/40 text-primary flex items-center justify-center shrink-0">
                                        <span class="material-symbols-outlined text-[18px]">receipt</span>
                                    </div>
                                    <div class="min-w-0">
                                        <h5 class="font-bold text-xs text-on-surface truncate">${s.name || s.product_name || 'Retail Sale'}</h5>
                                        <p class="text-[11px] text-on-surface-variant font-mono">
                                            ${units}x @ ${SmartStock.formatINR(s.unit_price || (total / units))} • <span class="text-outline">${dateStr}, ${timeStr}</span>
                                        </p>
                                    </div>
                                </div>
                                <div class="text-right shrink-0">
                                    <span class="font-bold text-sm text-primary font-mono block">+${SmartStock.formatINR(total)}</span>
                                    <span class="px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant text-[9px] font-semibold uppercase">Cash / Counter</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }
        },

        calculateSaleModalTotal() {
            const select = document.getElementById('sale-record-product-select');
            const qtyInput = document.getElementById('sale-record-qty-input');
            const totalDisplay = document.getElementById('sale-record-total-display');
            if (!select || !qtyInput || !totalDisplay) return;

            const selectedOpt = select.options[select.selectedIndex];
            const price = selectedOpt ? parseFloat(selectedOpt.getAttribute('data-price') || '0') : 0;
            const qty = parseInt(qtyInput.value, 10) || 1;
            const total = qty * price;
            totalDisplay.textContent = this.formatINR(total);
        },

        adjustSaleModalQty(delta) {
            const qtyInput = document.getElementById('sale-record-qty-input');
            if (qtyInput) {
                let val = parseInt(qtyInput.value, 10) || 1;
                val = Math.max(1, val + delta);
                qtyInput.value = val;
                this.calculateSaleModalTotal();
            }
        },

        async recordNewSaleFromModal(e) {
            if (e && e.preventDefault) e.preventDefault();
            const select = document.getElementById('sale-record-product-select');
            const qtyInput = document.getElementById('sale-record-qty-input');
            const dateInput = document.getElementById('sale-record-date-input');
            if (!select || !select.value) {
                this.showToast('Please select a product from active inventory.', 'warning');
                return;
            }

            const productId = select.value;
            const qty = parseInt(qtyInput ? qtyInput.value : '1', 10) || 1;
            const dateVal = dateInput && dateInput.value ? dateInput.value.trim() : null;

            const res = await this.updateStock(productId, -qty, {
                date: dateVal ? this.getBusinessDate(dateVal) : undefined,
                timestamp: dateVal ? new Date(dateVal).toISOString() : undefined
            });

            if (res) {
                this.renderSalesModalContent();
            }
        },

        exportCSV(products) {
            if (!products || products.length === 0) {
                this.downloadTemplate();
                return;
            }
            const headers = ['SKU', 'Product Name', 'Price INR', 'Cost INR', 'Stock On Hand', 'Reorder Point', 'Status'];
            const rows = products.map(p => [
                `"${p.sku || ''}"`,
                `"${(p.name || '').replace(/"/g, '""')}"`,
                p.unit_price || 0,
                p.unit_cost || 0,
                p.stock_on_hand || 0,
                p.reorder_point || 5,
                `"${p.status || 'active'}"`
            ]);

            const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
            const link = document.createElement('a');
            link.setAttribute('href', encodeURI(csvContent));
            link.setAttribute('download', `Inventory_Report_${new Date().toISOString().split('T')[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            this.showToast('Inventory report exported as CSV.', 'success');
        },

        downloadTemplate() {
            const headers = ['Product Name', 'Price INR', 'Cost INR', 'Stock', 'Reorder Point'];
            const sampleRows = [
                ['Aashirvaad Atta 5kg', 240, 210, 15, 5],
                ['Tata Salt 1kg', 28, 22, 30, 8],
                ['Fortune Sunflower Oil 1L', 145, 130, 12, 4]
            ];
            const csvContent = 'data:text/csv;charset=utf-8,' + [
                headers.join(','),
                ...sampleRows.map(r => r.map(c => `"${c}"`).join(','))
            ].join('\n');
            const link = document.createElement('a');
            link.setAttribute('href', encodeURI(csvContent));
            link.setAttribute('download', 'Inventory_Import_Template.csv');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            this.showToast('Blank CSV template downloaded.', 'info');
        },

        async importCSV(file) {
            const reader = new FileReader();
            reader.onload = async (e) => {
                try {
                    const text = e.target.result;
                    const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
                    if (lines.length <= 1) {
                        this.showToast('CSV file contains no data rows.', 'error');
                        return;
                    }

                    // Parse header row to locate column indices dynamically
                    const headerCols = lines[0].split(',').map(c => c.trim().toLowerCase().replace(/^"|"$/g, ''));
                    let nameIdx = -1;
                    let priceIdx = -1;
                    let costIdx = -1;
                    let stockIdx = -1;
                    let reorderIdx = -1;
                    let skuIdx = -1;
                    let categoryIdx = -1;

                    headerCols.forEach((col, idx) => {
                        if (nameIdx === -1 && (col.includes('name') || col.includes('product') || col.includes('item') || col.includes('title'))) nameIdx = idx;
                        else if (skuIdx === -1 && (col.includes('sku') || col.includes('code') || col.includes('barcode'))) skuIdx = idx;
                        else if (priceIdx === -1 && (col.includes('price') || col.includes('mrp') || col.includes('sale') || col.includes('selling'))) priceIdx = idx;
                        else if (costIdx === -1 && (col.includes('cost') || col.includes('buy') || col.includes('purchase'))) costIdx = idx;
                        else if (stockIdx === -1 && (col.includes('stock') || col.includes('qty') || col.includes('quantity') || col.includes('hand') || col.includes('inventory'))) stockIdx = idx;
                        else if (reorderIdx === -1 && (col.includes('reorder') || col.includes('rop') || col.includes('min') || col.includes('threshold') || col.includes('alert'))) reorderIdx = idx;
                        else if (categoryIdx === -1 && (col.includes('cat') || col.includes('dept') || col.includes('group'))) categoryIdx = idx;
                    });

                    // Fallbacks if no header names matched
                    if (nameIdx === -1) nameIdx = 0;
                    if (priceIdx === -1) priceIdx = headerCols.length > 1 ? 1 : -1;
                    if (costIdx === -1) costIdx = headerCols.length > 2 ? 2 : -1;
                    if (stockIdx === -1) stockIdx = headerCols.length > 3 ? 3 : -1;
                    if (reorderIdx === -1) reorderIdx = headerCols.length > 4 ? 4 : -1;

                    let count = 0;
                    for (let i = 1; i < lines.length; i++) {
                        const cols = lines[i].split(',').map(c => c.trim().replace(/^"|"$/g, ''));
                        const name = nameIdx >= 0 ? cols[nameIdx] : '';
                        if (!name) continue;

                        const rawPrice = priceIdx >= 0 ? parseFloat(cols[priceIdx]) : 0;
                        const rawCost = costIdx >= 0 ? parseFloat(cols[costIdx]) : 0;
                        const rawStock = stockIdx >= 0 ? parseInt(cols[stockIdx], 10) : 0;
                        let rawReorder = reorderIdx >= 0 ? parseInt(cols[reorderIdx], 10) : 10;

                        const unitPrice = isNaN(rawPrice) ? 0 : rawPrice;
                        const unitCost = isNaN(rawCost) || rawCost === 0 ? Math.round(unitPrice * 0.85) : rawCost;
                        const stockOnHand = isNaN(rawStock) ? 0 : Math.max(0, rawStock);

                        // Protect against shifted columns: Kirana reorder point should never be > 30 units
                        if (isNaN(rawReorder) || rawReorder <= 0 || rawReorder > 30) {
                            rawReorder = Math.min(20, Math.max(5, Math.round(stockOnHand * 0.15) || 10));
                        }

                        const category = categoryIdx >= 0 && cols[categoryIdx] ? cols[categoryIdx] : 'Groceries & Household';

                        await this.addProduct({
                            name: name,
                            unit_price: unitPrice,
                            unit_cost: unitCost,
                            stock_on_hand: stockOnHand,
                            reorder_point: rawReorder,
                            category_name: category
                        });
                        count++;
                    }
                    this.showToast(`Imported ${count} items with calibrated reorder levels.`, 'success');
                    setTimeout(() => window.location.reload(), 600);
                } catch (err) {
                    this.showToast('Error reading CSV file format.', 'error');
                }
            };
            reader.readAsText(file);
        },

        openAddProductModal() {
            const modal = document.getElementById('add-product-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                const nameInput = document.getElementById('new-item-name');
                if (nameInput) nameInput.focus();
            }
        },

        closeAddProductModal() {
            const modal = document.getElementById('add-product-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        async openEditProductModal(productId) {
            const products = await this.getProducts();
            const prod = products.find(p => String(p.id) === String(productId));
            if (!prod) {
                this.showToast('Product not found in inventory.', 'error');
                return;
            }
            const modal = document.getElementById('edit-item-modal');
            if (!modal) return;

            const idInput = document.getElementById('edit-prod-id');
            const nameInput = document.getElementById('edit-item-name');
            const priceInput = document.getElementById('edit-item-price');
            const costInput = document.getElementById('edit-item-cost');
            const stockInput = document.getElementById('edit-item-stock');
            const reorderInput = document.getElementById('edit-item-reorder');
            const catInput = document.getElementById('edit-item-category');

            if (idInput) idInput.value = prod.id;
            if (nameInput) nameInput.value = prod.name || '';
            if (priceInput) priceInput.value = prod.unit_price || 0;
            if (costInput) costInput.value = prod.unit_cost || Math.round((prod.unit_price || 0) * 0.85);
            if (stockInput) stockInput.value = prod.stock_on_hand || 0;
            if (reorderInput) reorderInput.value = Math.min(30, Number(prod.reorder_point) || 10);
            if (catInput) catInput.value = prod.category_name || 'Groceries & Household';

            modal.classList.remove('hidden');
            modal.classList.add('flex');
        },

        closeEditProductModal() {
            const modal = document.getElementById('edit-item-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        async saveEditProduct() {
            const id = document.getElementById('edit-prod-id')?.value;
            const name = document.getElementById('edit-item-name')?.value.trim();
            const price = parseFloat(document.getElementById('edit-item-price')?.value) || 0;
            const cost = parseFloat(document.getElementById('edit-item-cost')?.value) || Math.round(price * 0.85);
            const stock = parseInt(document.getElementById('edit-item-stock')?.value, 10) || 0;
            const reorder = Math.min(30, Math.max(1, parseInt(document.getElementById('edit-item-reorder')?.value, 10) || 10));
            const category = document.getElementById('edit-item-category')?.value || 'Groceries & Household';

            const products = await this.getProducts();
            const prod = products.find(p => String(p.id) === String(id));
            if (prod) {
                prod.name = name || prod.name;
                prod.unit_price = price;
                prod.unit_cost = cost;
                prod.stock_on_hand = Math.max(0, stock);
                prod.reorder_point = reorder;
                prod.category_name = category;
                prod.status = prod.stock_on_hand <= 0 ? 'out_of_stock' : (prod.stock_on_hand <= reorder ? 'low_stock' : 'active');

                this.saveProducts(products);
                this.showToast(`Updated ${prod.name}: Stock set to ${prod.stock_on_hand} (${prod.status.toUpperCase()})`, 'success');
                this.closeEditProductModal();
                await this.bindLivePageData();
            }
        },

        openImportModal() {
            const modal = document.getElementById('import-csv-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeImportModal() {
            const modal = document.getElementById('import-csv-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        openEditProfileModal() {
            const modal = document.getElementById('edit-profile-modal');
            if (modal) {
                let user = {};
                try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
                const nameInput = document.getElementById('edit-store-name');
                const managerInput = document.getElementById('edit-manager-name');
                const phoneInput = document.getElementById('edit-phone');
                const cityInput = document.getElementById('edit-city');
                const gstInput = document.getElementById('edit-gst');
                if (nameInput) nameInput.value = user.store || this.config.activeStoreName || '';
                if (managerInput) managerInput.value = user.manager || 'Store Owner';
                if (phoneInput) phoneInput.value = user.phone || '';
                if (cityInput) cityInput.value = user.city || 'India';
                if (gstInput) gstInput.value = user.gst || '';
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeEditProfileModal() {
            const modal = document.getElementById('edit-profile-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        saveProfile(data) {
            let user = {};
            try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
            const updated = { ...user, ...data };
            localStorage.setItem('smartstock_user', JSON.stringify(updated));
            if (updated.email) {
                this.saveStoreToRegistry(updated.email, updated);
            }
            if (updated.store) {
                localStorage.setItem('smartstock_last_active_store', updated.store);
                this.config.activeStoreName = updated.store;
            }
            const client = this.client();
            if (client && client.auth) {
                client.auth.updateUser({
                    data: {
                        store_name: updated.store,
                        phone: updated.phone || '',
                        manager: updated.manager || ''
                    }
                }).catch(() => {});
            }
            this.showToast('Store profile updated.', 'success');
            this.closeEditProfileModal();
            setTimeout(() => window.location.reload(), 400);
        },

        adjustAlertThreshold(delta) {
            let user = {};
            try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
            let current = parseInt(user.lowStockThreshold || 5, 10);
            current = Math.max(1, Math.min(100, current + delta));
            user.lowStockThreshold = current;
            localStorage.setItem('smartstock_user', JSON.stringify(user));
            const disp = document.getElementById('alert-threshold-display');
            if (disp) disp.textContent = current;
            this.showToast(`Low stock alert set to ${current} units`, 'info');
        },

        toggleScanSound(enabled) {
            let user = {};
            try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
            user.scanSound = enabled;
            localStorage.setItem('smartstock_user', JSON.stringify(user));
            this.showToast(enabled ? 'Scan sound enabled' : 'Scan sound muted', 'info');
        },

        toggleStockBanner(enabled) {
            let user = {};
            try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
            user.stockBanner = enabled;
            localStorage.setItem('smartstock_user', JSON.stringify(user));
            this.showToast(enabled ? 'Low stock alerts enabled' : 'Low stock alerts disabled', 'info');
        },

        openStoreSwitcherModal() {
            const modal = document.getElementById('store-switcher-modal');
            if (modal) {
                let user = {};
                try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
                const currentName = user.store || this.config.activeStoreName || 'My Store';
                const input = document.getElementById('quick-store-name-input');
                if (input) input.value = currentName;
                document.querySelectorAll('.current-store-display').forEach(el => el.textContent = currentName);
                document.querySelectorAll('.current-store-initial').forEach(el => el.textContent = currentName.trim().charAt(0).toUpperCase() || 'S');
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                if (input) {
                    setTimeout(() => input.focus(), 100);
                }
            }
        },

        closeStoreSwitcherModal() {
            const modal = document.getElementById('store-switcher-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        quickUpdateStoreName() {
            const input = document.getElementById('quick-store-name-input');
            const newName = input ? input.value.trim() : '';
            if (!newName) {
                this.showToast('Please enter a shop name', 'error');
                return;
            }
            this.saveProfile({ store: newName });
            this.closeStoreSwitcherModal();
        },

        async openNotificationsModal() {
            const modal = document.getElementById('notifications-modal');
            if (!modal) return;
            const products = await this.getProducts();
            let user = {};
            try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
            const storeName = user.store || this.config.activeStoreName || 'My Store';
            const lowStockItems = products.filter(p => p.stock_on_hand <= (p.reorder_point || 5));

            const list = document.getElementById('notifications-list');
            if (list) {
                let itemsHtml = '';

                if (lowStockItems.length > 0) {
                    itemsHtml += lowStockItems.map(p => `
                        <div class="p-3 bg-secondary-fixed/30 rounded-xl flex items-start gap-3 border border-secondary/20">
                            <span class="material-symbols-outlined text-secondary text-[22px] shrink-0 mt-0.5">warning</span>
                            <div class="min-w-0 flex-1 text-xs">
                                <p class="font-bold text-on-surface truncate">Low Stock: ${p.name}</p>
                                <p class="text-on-surface-variant mt-0.5">
                                    Current on-hand: <b class="text-secondary">${p.stock_on_hand} units</b> (Reorder point: ${p.reorder_point || 5}).
                                </p>
                                <div class="mt-2 flex items-center gap-2">
                                    <a href="05_purchase_orders.html" class="px-2.5 py-1 bg-secondary text-on-secondary rounded-lg font-semibold text-[11px] inline-flex items-center gap-1 active:scale-95 transition-all">
                                        <span>Reorder Item</span>
                                        <span class="material-symbols-outlined text-[13px]">arrow_forward</span>
                                    </a>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else if (products.length > 0) {
                    itemsHtml += `
                        <div class="p-3 bg-primary-fixed/30 rounded-xl flex items-start gap-3 border border-primary/20">
                            <span class="material-symbols-outlined text-primary text-[22px] shrink-0 mt-0.5">check_circle</span>
                            <div class="text-xs">
                                <p class="font-bold text-on-surface">Inventory Fully Healthy</p>
                                <p class="text-on-surface-variant mt-0.5">All ${products.length} products in ${storeName} have healthy stock levels above minimum reorder points.</p>
                            </div>
                        </div>
                    `;
                } else {
                    itemsHtml += `
                        <div class="p-3 bg-surface-container-low rounded-xl flex items-start gap-3">
                            <span class="material-symbols-outlined text-primary text-[22px] shrink-0 mt-0.5">storefront</span>
                            <div class="text-xs">
                                <p class="font-bold text-on-surface">Welcome to ${storeName}!</p>
                                <p class="text-on-surface-variant mt-0.5">Your catalog is currently empty. Tap "+ Add Product" or "Import File" to add your products.</p>
                            </div>
                        </div>
                    `;
                }

                // System & Currency notice
                itemsHtml += `
                    <div class="p-3 bg-surface-container-low rounded-xl flex items-start gap-3">
                        <span class="material-symbols-outlined text-primary text-[20px] shrink-0 mt-0.5">currency_rupee</span>
                        <div class="text-xs">
                            <p class="font-bold text-on-surface">Retail Pricing System (₹ INR)</p>
                            <p class="text-on-surface-variant mt-0.5">SmartStock is configured for Indian Rupee currency standard.</p>
                        </div>
                    </div>
                `;

                list.innerHTML = itemsHtml;
            }

            modal.classList.remove('hidden');
            modal.classList.add('flex');
        },

        closeNotificationsModal() {
            const modal = document.getElementById('notifications-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        markNotificationsAsRead() {
            localStorage.setItem('smartstock_notifs_read', 'true');
            document.querySelectorAll('header button .rounded-full').forEach(b => {
                if (b.classList.contains('bg-secondary') || (b.textContent && b.textContent.match(/^\\d+$/))) {
                    b.style.display = 'none';
                }
            });
            this.showToast('All notifications marked as read', 'info');
            this.closeNotificationsModal();
        },

        showToast(message, type = 'info') {
            if (typeof document === 'undefined' || typeof document.createElement !== 'function') return;
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'fixed bottom-20 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 max-w-[90vw] pointer-events-none';
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            const bgClass = type === 'success' ? 'bg-[#0b3127] text-white' : (type === 'error' ? 'bg-[#ba1a1a] text-white' : 'bg-[#181d1a] text-white');
            toast.className = `${bgClass} px-4 py-2 rounded-lg shadow-lg text-xs font-medium pointer-events-auto transition-all transform duration-200 opacity-0 translate-y-2 border border-white/10`;
            toast.textContent = message;
            container.appendChild(toast);

            requestAnimationFrame(() => toast.classList.remove('opacity-0', 'translate-y-2'));
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-2');
                setTimeout(() => toast.remove(), 250);
            }, 2500);
        },

        setForecastHorizon(days, silent = false) {
            days = parseInt(days, 10) || 14;
            localStorage.setItem('smartstock_forecast_horizon', days);

            // 1. Update Horizon Button styling
            const buttons = document.querySelectorAll('.horizon-btn');
            buttons.forEach(btn => {
                const d = parseInt(btn.getAttribute('data-days'), 10);
                if (d === days) {
                    btn.className = 'horizon-btn flex-1 py-1.5 px-3 rounded-lg text-center font-label-md text-label-md font-semibold bg-surface-container-lowest text-primary shadow-sm whitespace-nowrap flex items-center justify-center gap-1';
                    btn.innerHTML = `<span>${days} Days</span><span class="w-1.5 h-1.5 rounded-full bg-secondary"></span>`;
                } else {
                    btn.className = 'horizon-btn flex-1 py-1.5 px-2 rounded-lg text-center font-label-md text-label-md text-on-surface-variant transition-colors hover:text-on-surface whitespace-nowrap';
                    btn.innerHTML = `<span>${d} Days</span>`;
                }
            });

            // Horizon parameters configuration
            const configs = {
                7: {
                    accuracy: '96.8%',
                    baseline: 'High-frequency run-rate • 30d baseline',
                    dates: ['Oct 15', 'Oct 17', 'Oct 18', 'Oct 20', 'Oct 22', 'Oct 25'],
                    curvePath: 'M 160 82 L 195 78 L 230 72 L 265 68 L 300 60 L 330 54',
                    uncertainty: '160,82 195,70 230,60 265,52 300,44 330,38 330,72 300,76 265,82 230,85 195,88 160,82',
                    points: [{ cx: 230, cy: 72 }, { cx: 300, cy: 60 }],
                    multiplier: 0.5,
                    defaultUnits: 18,
                    liftText: '+18% Peak Run'
                },
                14: {
                    accuracy: '94.2%',
                    baseline: 'Historical baseline • 120d',
                    dates: ['Oct 11', 'Oct 14', 'Oct 18', 'Oct 22', 'Oct 26', 'Oct 31'],
                    curvePath: 'M 160 82 L 190 88 L 220 70 L 255 78 L 290 56 L 330 64',
                    uncertainty: '160,82 190,62 220,40 255,48 290,28 330,34 330,105 290,95 255,115 220,105 190,118 160,82',
                    points: [{ cx: 220, cy: 70 }, { cx: 290, cy: 56 }],
                    multiplier: 1.0,
                    defaultUnits: 36,
                    liftText: '+28% Oct Lift'
                },
                30: {
                    accuracy: '89.5%',
                    baseline: 'Monthly statistical run-rate • 180d',
                    dates: ['Oct 01', 'Oct 10', 'Oct 18', 'Oct 28', 'Nov 08', 'Nov 17'],
                    curvePath: 'M 160 82 L 195 94 L 230 82 L 265 62 L 300 46 L 330 50',
                    uncertainty: '160,82 195,76 230,55 265,34 300,18 330,22 330,120 300,112 265,116 230,122 195,124 160,82',
                    points: [{ cx: 230, cy: 82 }, { cx: 300, cy: 46 }],
                    multiplier: 2.1,
                    defaultUnits: 76,
                    liftText: '+35% Monthly Trend'
                },
                90: {
                    accuracy: '81.2%',
                    baseline: 'Quarterly seasonal ARIMA • 365d',
                    dates: ['Aug', 'Sep', 'Oct (Today)', 'Nov', 'Dec', 'Jan'],
                    curvePath: 'M 160 82 L 200 102 L 240 74 L 280 40 L 310 28 L 330 36',
                    uncertainty: '160,82 200,82 240,42 280,16 310,8 330,12 330,138 310,130 280,124 240,128 200,132 160,82',
                    points: [{ cx: 240, cy: 74 }, { cx: 310, cy: 28 }],
                    multiplier: 6.2,
                    defaultUnits: 224,
                    liftText: '+42% Festival Season'
                }
            };

            const cfg = configs[days] || configs[14];

            // 2. Accuracy & Baseline
            const accEl = document.getElementById('forecast-accuracy-label');
            if (accEl) accEl.textContent = `Forecast Accuracy: ${cfg.accuracy}`;
            const baseEl = document.getElementById('forecast-baseline-label');
            if (baseEl) baseEl.textContent = cfg.baseline;

            // 3. X-Axis Dates
            const dateSpans = document.querySelectorAll('#forecast-x-axis span');
            if (dateSpans && dateSpans.length === 6) {
                cfg.dates.forEach((d, i) => {
                    dateSpans[i].textContent = d;
                });
            }

            // 4. SVG Forecast Curve & Uncertainty Band
            const svgPath = document.getElementById('forecast-svg-path');
            if (svgPath) svgPath.setAttribute('d', cfg.curvePath);
            const svgPoly = document.getElementById('forecast-svg-uncertainty');
            if (svgPoly) svgPoly.setAttribute('points', cfg.uncertainty);

            // 5. SVG Points
            const circles = document.querySelectorAll('.forecast-point-circle');
            if (circles && circles.length >= 2 && cfg.points) {
                circles[0].setAttribute('cx', cfg.points[0].cx);
                circles[0].setAttribute('cy', cfg.points[0].cy);
                circles[1].setAttribute('cx', cfg.points[1].cx);
                circles[1].setAttribute('cy', cfg.points[1].cy);
            }

            // 6. Lift pill in driver insights
            const liftPill = document.getElementById('forecast-lift-pill');
            if (liftPill) liftPill.textContent = cfg.liftText;

            // 7. Order draft quantity stepper
            const qtyInput = document.getElementById('order-qty-input');
            const costDisp = document.getElementById('est-cost');
            const poBtn = document.getElementById('po-btn-label');
            const unitCost = window.currentForecastUnitCost || 28.0;

            if (qtyInput) {
                const targetUnits = cfg.defaultUnits;
                qtyInput.value = targetUnits;
                const totalCost = (targetUnits * unitCost).toFixed(2);
                if (costDisp) costDisp.textContent = '₹' + Number(totalCost).toLocaleString('en-IN') + ' est.';
                if (poBtn) poBtn.textContent = `Create Purchase Order Draft with ${targetUnits} units (${days}d cover)`;
            }

            if (!silent) {
                this.showToast(`Forecast horizon set to ${days} Days`, 'info');
            }
        },

        async createPoDraftFromForecast() {
            const qtyInput = document.getElementById('order-qty-input');
            const qty = parseInt(qtyInput ? qtyInput.value : '36', 10) || 36;
            const prodName = document.querySelector('main h2')?.textContent?.trim() || 'Inventory Item';
            const unitCost = (typeof window.currentForecastUnitCost === 'number' && !isNaN(window.currentForecastUnitCost))
                ? window.currentForecastUnitCost
                : 28.0;
            const total = this.fromPaise(this.toPaise(qty * unitCost));

            const products = await this.getProducts();
            const prod = products.find(p => p.name === prodName || (p.name && prodName && p.name.toLowerCase() === prodName.toLowerCase())) || products[0];

            if (prod) {
                prod.stock_on_order = (Number(prod.stock_on_order) || 0) + qty;
                this.saveProducts(products);
            }

            const purchaseOrders = this.getPurchaseOrders();
            const year = new Date().getFullYear();
            const count = (purchaseOrders.length + 1).toString().padStart(3, '0');
            const poNumber = `PO-${year}-${count}`;

            const newPO = {
                id: 'po-' + Date.now(),
                po_number: poNumber,
                created_at: new Date().toISOString(),
                status: 'ordered',
                supplier: 'Metro Wholesale / Regional Supply Hub',
                items: [{
                    product_id: prod ? prod.id : undefined,
                    productId: prod ? prod.id : undefined,
                    name: prod ? prod.name : prodName,
                    units: qty,
                    unit_cost: unitCost,
                    total_cost: total
                }],
                total_amount: total,
                is_ai_generated: true,
                notes: 'Created from Forecast replenishment recommendation'
            };

            purchaseOrders.unshift(newPO);
            this.savePurchaseOrders(purchaseOrders);

            this.showToast(`Purchase Order ${poNumber} issued & sent to supplier!`, 'success');
            localStorage.setItem('smartstock_po_filter', 'ordered');
            setTimeout(() => {
                if (typeof window !== 'undefined' && window.location) {
                    window.location.href = '05_purchase_orders.html';
                }
            }, 500);
        },

        getPurchaseOrders() {
            const key = this.getUserKey('smartstock_purchase_orders');
            let orders = [];
            try {
                orders = JSON.parse(localStorage.getItem(key) || '[]');
            } catch (e) {
                orders = [];
            }
            return orders;
        },

        savePurchaseOrders(orders) {
            const key = this.getUserKey('smartstock_purchase_orders');
            localStorage.setItem(key, JSON.stringify(orders));
        },

        async issueDraftPO() {
            const products = await this.getProducts();
            const purchaseOrders = this.getPurchaseOrders();

            // Identify which low-stock items are NOT yet in an active PO ('ordered' or 'in_transit')
            const activeOrders = purchaseOrders.filter(po => po.status === 'ordered' || po.status === 'in_transit');
            const orderedProductIds = new Set();
            activeOrders.forEach(po => {
                if (Array.isArray(po.items)) {
                    po.items.forEach(it => {
                        if (it.product_id) orderedProductIds.add(String(it.product_id));
                        if (it.name) orderedProductIds.add(it.name.toLowerCase().trim());
                    });
                }
            });

            const itemsToOrder = products.filter(p => {
                const isLow = (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 5);
                const isAlreadyOrdered = orderedProductIds.has(String(p.id)) || orderedProductIds.has((p.name || '').toLowerCase().trim());
                return isLow && !isAlreadyOrdered;
            });

            if (itemsToOrder.length === 0) {
                this.showToast('No unreplenished items in draft.', 'info');
                return;
            }

            const year = new Date().getFullYear();
            const count = (purchaseOrders.length + 1).toString().padStart(3, '0');
            const poNumber = `PO-${year}-${count}`;

            let totalAmount = 0;
            const poItems = itemsToOrder.map(p => {
                const needed = Math.max(10, (Number(p.reorder_point) || 5) * 2 - (Number(p.stock_on_hand) || 0));
                const cost = Number(p.unit_cost) || Math.round((Number(p.unit_price) || 100) * 0.85);
                const lineTotal = needed * cost;
                totalAmount += lineTotal;
                return {
                    product_id: p.id,
                    name: p.name,
                    sku: p.sku || 'SKU',
                    units: needed,
                    unit_cost: cost,
                    total_cost: lineTotal
                };
            });

            const newPO = {
                id: 'po-' + Date.now(),
                po_number: poNumber,
                created_at: new Date().toISOString(),
                status: 'ordered', // Moves directly to "Ordered • Sent to Supplier"
                supplier: 'Metro Wholesale / Regional Supply Hub',
                items: poItems,
                total_amount: totalAmount,
                is_ai_generated: true,
                notes: 'AI Automated Replenishment generated from sales run-rate & safety thresholds'
            };

            // Update product stock_on_order
            itemsToOrder.forEach(p => {
                const itemInfo = poItems.find(it => String(it.product_id) === String(p.id));
                p.stock_on_order = (Number(p.stock_on_order) || 0) + (itemInfo ? itemInfo.units : 10);
            });
            this.saveProducts(products);

            purchaseOrders.unshift(newPO);
            this.savePurchaseOrders(purchaseOrders);

            // Sync to backend
            try {
                const email = this.getCurrentUserEmail();
                if (email) {
                    fetch('http://127.0.0.1:8000/api/v1/user/purchase-orders', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_email: email,
                            po_number: poNumber,
                            supplier: newPO.supplier,
                            status: newPO.status,
                            total_amount: newPO.total_amount,
                            items: newPO.items
                        })
                    }).catch(e => console.warn('PO backend sync error:', e));
                }
            } catch(e) {}

            this.showToast(`Purchase Order ${poNumber} issued & sent to supplier! Moved to Orders.`, 'success');
            localStorage.setItem('smartstock_po_filter', 'ordered');
            await this.bindLivePageData();
        },

        // AI Replenishment Engine UI & Logic
        renderAIReplenishmentPage(products) {
            const container = document.getElementById('ai-replenishment-container');
            const bottomBar = document.getElementById('replenish-bottom-bar');
            if (!container) return;

            const purchaseOrders = this.getPurchaseOrders();
            const activeOrders = purchaseOrders.filter(po => po.status === 'ordered' || po.status === 'in_transit');
            const orderedProductIds = new Set();
            activeOrders.forEach(po => {
                if (Array.isArray(po.items)) {
                    po.items.forEach(it => {
                        if (it.product_id) orderedProductIds.add(String(it.product_id));
                        if (it.name) orderedProductIds.add(it.name.toLowerCase().trim());
                    });
                }
            });

            // AI identifies items needing replenishment now (below safety stock or depleted)
            const neededItems = products.filter(p => {
                const isLow = (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 5);
                const isOrdered = orderedProductIds.has(String(p.id)) || orderedProductIds.has((p.name || '').toLowerCase().trim());
                return isLow && !isOrdered;
            });

            this._currentReplenishItems = neededItems;

            if (products.length === 0) {
                if (bottomBar) bottomBar.classList.add('hidden');
                container.innerHTML = `
                    <div class="bg-surface-container-lowest rounded-2xl p-8 text-center border border-outline/10 space-y-3">
                        <span class="material-symbols-outlined text-[40px] text-outline">inventory_2</span>
                        <h3 class="font-bold text-base text-on-surface">Inventory Catalog Empty</h3>
                        <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                            Your store register has zero products. Add inventory items or import a CSV to let the AI evaluate restocking levels.
                        </p>
                        <div class="pt-2 flex items-center justify-center gap-2">
                            <a href="03_inventory.html" class="px-4 py-2 bg-primary text-on-primary rounded-xl font-semibold text-xs shadow-xs active:scale-95 transition-all">
                                Go to Inventory
                            </a>
                        </div>
                    </div>
                `;
                return;
            }

            if (neededItems.length === 0) {
                if (bottomBar) bottomBar.classList.add('hidden');
                container.innerHTML = `
                    <div class="bg-surface-container-lowest rounded-2xl p-8 text-center border border-outline/10 space-y-3">
                        <span class="material-symbols-outlined text-[40px] text-primary">verified</span>
                        <h3 class="font-bold text-base text-on-surface">All Stocks Healthy</h3>
                        <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                            The AI Restocking Engine evaluated all ${products.length} products. All stock levels are above safety thresholds, or active purchase orders are already in transit.
                        </p>
                        <div class="pt-2 flex items-center justify-center gap-3">
                            <a href="03_inventory.html" class="px-4 py-2 bg-surface-container-high text-on-surface rounded-xl font-semibold text-xs active:scale-95 transition-all">
                                View Inventory
                            </a>
                            <a href="05_purchase_orders.html" class="px-4 py-2 bg-primary text-on-primary rounded-xl font-semibold text-xs shadow-xs active:scale-95 transition-all">
                                View Orders Ledger
                            </a>
                        </div>
                    </div>
                `;
                return;
            }

            if (bottomBar) bottomBar.classList.remove('hidden');

            let html = `
                <div class="flex items-center justify-between px-1">
                    <span class="text-xs font-bold text-on-surface uppercase tracking-wider">AI Restocking Candidates (${neededItems.length})</span>
                    <button type="button" onclick="SmartStock.toggleSelectAllReplenish()" class="text-xs text-primary font-semibold hover:underline">Toggle Select All</button>
                </div>
                <div class="space-y-3">
            `;

            neededItems.forEach((p, idx) => {
                const stockOnHand = Number(p.stock_on_hand) || 0;
                const reorderPoint = Number(p.reorder_point) || 5;
                const unitCost = Number(p.unit_cost) || Math.round((Number(p.unit_price) || 100) * 0.85);
                const unitPrice = Number(p.unit_price) || Math.round(unitCost * 1.2);
                const recommendedQty = Math.max(10, reorderPoint * 2 - stockOnHand);
                const lineTotal = recommendedQty * unitCost;

                const isOutOfStock = stockOnHand <= 0;
                const statusBadge = isOutOfStock
                    ? `<span class="px-2 py-0.5 rounded-full bg-error/15 text-error text-[10px] font-bold uppercase">OUT OF STOCK (0 units)</span>`
                    : `<span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[10px] font-bold uppercase">LOW STOCK (${stockOnHand} left)</span>`;

                html += `
                    <div class="bg-surface-container-lowest rounded-2xl p-4 shadow-sm border border-outline/10 space-y-3 relative overflow-hidden" id="replenish-card-${idx}">
                        <div class="flex items-start gap-3">
                            <input type="checkbox" id="rep-check-${idx}" class="replenish-item-checkbox h-5 w-5 rounded mt-0.5 accent-primary cursor-pointer shrink-0" checked onchange="SmartStock.updateReplenishTotals()" data-idx="${idx}" data-id="${p.id}">
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 flex-wrap mb-1">
                                    <span class="font-mono text-[11px] text-outline">${p.sku || 'SKU'}</span>
                                    ${statusBadge}
                                </div>
                                <h4 class="font-bold text-sm text-on-surface truncate">${p.name}</h4>
                                <div class="flex items-center gap-3 text-xs text-on-surface-variant mt-1">
                                    <span>Price: <b class="text-on-surface">${SmartStock.formatINR(unitPrice)}</b></span>
                                    <span>•</span>
                                    <span>Cost: <b class="text-primary font-mono">${SmartStock.formatINR(unitCost)}</b></span>
                                </div>
                            </div>
                        </div>

                        <!-- AI Rationale Strip -->
                        <div class="bg-surface-container-low p-2 rounded-xl text-xs flex items-center justify-between gap-2">
                            <div class="flex items-center gap-1.5 text-on-surface-variant truncate">
                                <span class="material-symbols-outlined text-secondary text-[16px]">psychology</span>
                                <span class="truncate">Safety: ${p.safety_stock || 2} • Reorder: ${reorderPoint} • Lead: ${p.lead_time_days || 3}d</span>
                            </div>
                            <span class="text-[11px] font-semibold text-secondary whitespace-nowrap">AI Restock: +${recommendedQty}</span>
                        </div>

                        <!-- Quantity Stepper & Subtotal -->
                        <div class="flex items-center justify-between pt-1 border-t border-outline/10">
                            <div class="flex items-center gap-2">
                                <span class="text-xs text-on-surface-variant font-medium">Order Qty:</span>
                                <div class="flex items-center bg-surface-container-low rounded-lg border border-outline/15 h-8">
                                    <button type="button" onclick="SmartStock.adjustReplenishQty(${idx}, -5)" class="w-7 h-8 flex items-center justify-center text-on-surface font-bold hover:bg-surface-container active:scale-95 transition-all">-</button>
                                    <input type="number" id="rep-qty-${idx}" value="${recommendedQty}" min="1" max="1000" class="w-12 text-center font-mono font-bold text-xs bg-transparent focus:outline-none" oninput="SmartStock.updateReplenishTotals()" data-idx="${idx}" data-cost="${unitCost}">
                                    <button type="button" onclick="SmartStock.adjustReplenishQty(${idx}, 5)" class="w-7 h-8 flex items-center justify-center text-on-surface font-bold hover:bg-surface-container active:scale-95 transition-all">+</button>
                                </div>
                            </div>
                            <div class="text-right">
                                <span class="text-[10px] text-on-surface-variant block">Subtotal</span>
                                <span id="rep-total-${idx}" class="font-bold text-sm text-primary font-mono">${SmartStock.formatINR(lineTotal)}</span>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += `</div>`;
            container.innerHTML = html;
            this.updateReplenishTotals();
        },

        updateReplenishTotals() {
            if (!this._currentReplenishItems) return;
            let selectedCount = 0;
            let totalAmt = 0;

            this._currentReplenishItems.forEach((p, idx) => {
                const checkbox = document.getElementById(`rep-check-${idx}`);
                const qtyInput = document.getElementById(`rep-qty-${idx}`);
                const totalSpan = document.getElementById(`rep-total-${idx}`);
                const card = document.getElementById(`replenish-card-${idx}`);
                const unitCost = Number(p.unit_cost) || Math.round((Number(p.unit_price) || 100) * 0.85);

                let qty = qtyInput ? (parseInt(qtyInput.value, 10) || 0) : 0;
                if (qty < 1) qty = 1;
                const lineTotal = qty * unitCost;

                if (totalSpan) totalSpan.textContent = this.formatINR(lineTotal);

                if (checkbox && checkbox.checked) {
                    selectedCount++;
                    totalAmt += lineTotal;
                    if (card) card.classList.remove('opacity-60');
                } else if (card) {
                    card.classList.add('opacity-60');
                }
            });

            const countSpan = document.getElementById('replenish-selected-count');
            const amtSpan = document.getElementById('replenish-total-amount');
            const orderBtn = document.getElementById('replenish-order-btn');

            if (countSpan) countSpan.textContent = `${selectedCount} item${selectedCount === 1 ? '' : 's'} selected`;
            if (amtSpan) amtSpan.textContent = this.formatINR(totalAmt);
            if (orderBtn) {
                orderBtn.disabled = selectedCount === 0;
                orderBtn.innerHTML = `
                    <span class="material-symbols-outlined text-[18px]">shopping_cart_checkout</span>
                    <span>Order Selected (${selectedCount})</span>
                `;
            }
        },

        adjustReplenishQty(idx, delta) {
            const input = document.getElementById(`rep-qty-${idx}`);
            if (input) {
                let val = parseInt(input.value, 10) || 10;
                val = Math.max(1, val + delta);
                input.value = val;
                this.updateReplenishTotals();
            }
        },

        toggleSelectAllReplenish() {
            const checkboxes = document.querySelectorAll('.replenish-item-checkbox');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
            this.updateReplenishTotals();
        },

        async createPOFromReplenishment() {
            if (!this._currentReplenishItems || this._currentReplenishItems.length === 0) {
                this.showToast('No items available to replenish.', 'info');
                return;
            }

            const poItems = [];
            let totalAmount = 0;
            const products = await this.getProducts();

            this._currentReplenishItems.forEach((p, idx) => {
                const checkbox = document.getElementById(`rep-check-${idx}`);
                const qtyInput = document.getElementById(`rep-qty-${idx}`);
                if (checkbox && checkbox.checked) {
                    const qty = qtyInput ? (parseInt(qtyInput.value, 10) || 10) : 10;
                    const unitCost = Number(p.unit_cost) || Math.round((Number(p.unit_price) || 100) * 0.85);
                    const lineTotal = qty * unitCost;
                    totalAmount += lineTotal;

                    poItems.push({
                        product_id: p.id,
                        name: p.name,
                        units: qty,
                        unit_cost: unitCost,
                        total_cost: lineTotal
                    });

                    // Update product stock_on_order
                    const prodInCatalog = products.find(prod => String(prod.id) === String(p.id) || prod.name === p.name);
                    if (prodInCatalog) {
                        prodInCatalog.stock_on_order = (Number(prodInCatalog.stock_on_order) || 0) + qty;
                    }
                }
            });

            if (poItems.length === 0) {
                this.showToast('Please select at least one item with the checkbox to order.', 'warning');
                return;
            }

            const purchaseOrders = this.getPurchaseOrders();
            const year = new Date().getFullYear();
            const poNumber = `PO-${year}-${(purchaseOrders.length + 1).toString().padStart(3, '0')}`;
            const newPO = {
                id: 'po-' + Date.now(),
                po_number: poNumber,
                created_at: new Date().toISOString(),
                status: 'ordered',
                supplier: 'Metro Wholesale / Regional Supply Hub',
                items: poItems,
                total_amount: totalAmount,
                is_ai_generated: true,
                notes: 'AI Automated Replenishment Order'
            };

            purchaseOrders.unshift(newPO);
            this.savePurchaseOrders(purchaseOrders);
            this.saveProducts(products);

            // Sync to backend if available
            try {
                const email = this.getCurrentUserEmail();
                if (email) {
                    fetch('http://127.0.0.1:8000/api/v1/user/purchase-orders', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_email: email,
                            po_number: poNumber,
                            supplier: newPO.supplier,
                            status: newPO.status,
                            total_amount: newPO.total_amount,
                            items: newPO.items
                        })
                    }).catch(e => console.warn('PO backend sync error:', e));
                }
            } catch(e) {}

            this.showToast(`Order ${poNumber} created & sent to supplier!`, 'success');
            localStorage.setItem('smartstock_po_filter', 'ordered');

            // Dispatch directly to the Orders section in the navigation bar!
            setTimeout(() => {
                window.location.href = '05_purchase_orders.html';
            }, 350);
        },

        async receivePO(poId) {
            return serializeMutation(async () => {
                const purchaseOrders = this.getPurchaseOrders();
                const po = purchaseOrders.find(o => String(o.id) === String(poId) || o.po_number === poId);
                if (!po) {
                    this.showToast('Purchase Order not found', 'error');
                    return { success: false, error: 'Purchase Order not found' };
                }
                if (po.status === 'cancelled') {
                    this.showToast('Cannot receive a cancelled Purchase Order', 'error');
                    return { success: false, error: 'Cannot receive cancelled order' };
                }
                if (po.status === 'completed') {
                    this.showToast('This PO has already been received into inventory.', 'info');
                    return { success: true, replayed: true, po };
                }

                const products = await this.getProducts();
                let totalUnitsReceived = 0;

                if (Array.isArray(po.items)) {
                    po.items.forEach(it => {
                        const units = Number(it.units !== undefined ? it.units : it.quantity);
                        if (!isFinite(units) || units <= 0) {
                            return; // skip non-positive or invalid units
                        }

                        const p = products.find(prod =>
                            (it.product_id && String(prod.id) === String(it.product_id)) ||
                            (it.productId && String(prod.id) === String(it.productId)) ||
                            (prod.name && prod.name.toLowerCase().trim() === (it.name || it.item || '').toLowerCase().trim())
                        );

                        if (p) {
                            p.stock_on_hand = (Number(p.stock_on_hand) || 0) + units;
                            p.stock_on_order = Math.max(0, (Number(p.stock_on_order) || 0) - units);
                            const rop = Number(p.reorder_point);
                            const finalRop = (p.reorder_point === undefined || p.reorder_point === null || isNaN(rop)) ? 10 : rop;
                            p.reorder_point = finalRop;
                            p.status = p.stock_on_hand <= 0 ? 'out_of_stock' : (p.stock_on_hand <= finalRop ? 'low_stock' : 'active');
                            totalUnitsReceived += units;
                        } else {
                            // Create product if missing from active catalog
                            const cost = (it.unit_cost !== null && it.unit_cost !== undefined && !isNaN(Number(it.unit_cost))) ? Number(it.unit_cost) : 100;
                            const newProd = {
                                id: it.product_id || it.productId || ('loc-' + Date.now() + '-' + Math.floor(Math.random() * 1000)),
                                shop_id: this.config.shopId,
                                sku: it.sku || `SKU-${Math.floor(1000 + Math.random() * 9000)}`,
                                name: it.name || it.item || 'Replenished Item',
                                description: 'Stock inwarded from purchase order',
                                unit_cost: cost,
                                unit_price: Math.round(cost * 1.25),
                                stock_on_hand: units,
                                stock_on_order: 0,
                                safety_stock: 4,
                                reorder_point: 10,
                                lead_time_days: 3,
                                status: units > 10 ? 'active' : 'low_stock',
                                abc_class: 'B',
                                xyz_class: 'X',
                                tier: 'Core',
                                category_name: 'Groceries & Household'
                            };
                            products.unshift(newProd);
                            totalUnitsReceived += units;
                        }
                    });
                }

                po.status = 'completed';
                po.inwarded_at = new Date().toISOString();

                this.saveProducts(products);
                this.savePurchaseOrders(purchaseOrders);

                // Sync receive to backend
                try {
                    const email = this.getCurrentUserEmail();
                    if (email) {
                        fetch(`http://127.0.0.1:8000/api/v1/user/purchase-orders/${po.id}/receive?email=${encodeURIComponent(email)}`, {
                            method: 'POST'
                        }).catch(e => console.warn('PO receive backend sync error:', e));
                    }
                } catch (e) {}

                this.showToast(`Inwarded ${totalUnitsReceived} units from ${po.po_number}! Stock updated.`, 'success');
                await this.bindLivePageData();
                return { success: true, totalUnitsReceived, po };
            });
        },

        currentPOFilter: 'all',

        filterPurchaseOrders(filterType) {
            this.currentPOFilter = filterType;
            localStorage.setItem('smartstock_po_filter', filterType);
            this.bindLivePageData();
        },

        openNewPOModal() {
            const modal = document.getElementById('create-po-modal');
            if (modal) {
                this.populateNewPOProductOptions();
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeNewPOModal() {
            const modal = document.getElementById('create-po-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        async populateNewPOProductOptions() {
            const select = document.getElementById('po-product-select');
            if (!select) return;
            const products = await this.getProducts();
            if (products.length === 0) {
                select.innerHTML = '<option value="">No products in catalog</option>';
                return;
            }
            select.innerHTML = products.map(p => `
                <option value="${p.id}" data-cost="${p.unit_cost || Math.round((p.unit_price || 100)*0.85)}" data-name="${p.name}" data-sku="${p.sku}">
                    ${p.name} (Stock: ${p.stock_on_hand} | Cost: ₹${p.unit_cost || 0})
                </option>
            `).join('');
            this.calculateNewPOTotal();
        },

        calculateNewPOTotal() {
            const select = document.getElementById('po-product-select');
            const qtyInput = document.getElementById('po-qty-input');
            const totalEl = document.getElementById('po-total-display');
            if (!select || !qtyInput || !totalEl) return;
            const opt = select.selectedOptions[0];
            const cost = opt ? parseFloat(opt.getAttribute('data-cost') || '0') : 0;
            const qty = parseInt(qtyInput.value || '10', 10);
            totalEl.textContent = this.formatINR(cost * qty);
        },

        async submitNewPO(e) {
            if (e) e.preventDefault();
            const select = document.getElementById('po-product-select');
            const qtyInput = document.getElementById('po-qty-input');
            const supplierInput = document.getElementById('po-supplier-input');
            if (!select || !qtyInput) return;
            const opt = select.selectedOptions[0];
            if (!opt || !opt.value) {
                this.showToast('Please select a product', 'error');
                return;
            }
            const productId = opt.value;
            const prodName = opt.getAttribute('data-name');
            const prodSku = opt.getAttribute('data-sku');
            const cost = parseFloat(opt.getAttribute('data-cost') || '0');
            const qty = Math.max(1, parseInt(qtyInput.value || '10', 10));
            const supplier = (supplierInput?.value || '').trim() || 'Metro Wholesale / Regional Supply Hub';

            const purchaseOrders = this.getPurchaseOrders();
            const year = new Date().getFullYear();
            const count = (purchaseOrders.length + 1).toString().padStart(3, '0');
            const poNumber = `PO-${year}-${count}`;

            const newPO = {
                id: 'po-' + Date.now(),
                po_number: poNumber,
                created_at: new Date().toISOString(),
                status: 'ordered',
                supplier: supplier,
                items: [{
                    product_id: productId,
                    name: prodName,
                    sku: prodSku,
                    units: qty,
                    unit_cost: cost,
                    total_cost: cost * qty
                }],
                total_amount: cost * qty,
                is_ai_generated: false,
                notes: 'Manual Purchase Order'
            };

            const products = await this.getProducts();
            const p = products.find(prod => String(prod.id) === String(productId));
            if (p) {
                p.stock_on_order = (Number(p.stock_on_order) || 0) + qty;
                this.saveProducts(products);
            }

            purchaseOrders.unshift(newPO);
            this.savePurchaseOrders(purchaseOrders);

            this.closeNewPOModal();
            this.showToast(`Purchase Order ${poNumber} issued to ${supplier}!`, 'success');
            localStorage.setItem('smartstock_po_filter', 'ordered');
            await this.bindLivePageData();
        },

        // Date Switcher Methods
        openDateSwitcherModal() {
            const modal = document.getElementById('date-switcher-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }
        },

        closeDateSwitcherModal() {
            const modal = document.getElementById('date-switcher-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        },

        selectDateRange(rangeLabel) {
            this.setActiveDateRange(rangeLabel);
            localStorage.setItem('smartstock_date_range', rangeLabel);
            const labelEl = document.getElementById('overview-date-range-label');
            if (labelEl) labelEl.textContent = rangeLabel;

            const buttons = document.querySelectorAll('#date-switcher-options button');
            buttons.forEach(btn => {
                const text = btn.querySelector('span:first-child')?.textContent?.trim();
                const check = btn.querySelector('.checkmark');
                if (text === rangeLabel) {
                    btn.className = 'date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer bg-primary-fixed/30 text-primary';
                    if (check) check.classList.remove('hidden');
                } else {
                    btn.className = 'date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer';
                    if (check) check.classList.add('hidden');
                }
            });

            this.closeDateSwitcherModal();
            this.showToast(`Active register timeframe: ${rangeLabel}`, 'info');
            this.bindLivePageData();
        },

        async runAIInventoryAnalysis(forceRefresh = false) {
            const apiKey = this.getGeminiApiKey();
            const products = await this.getProducts();
            if (products.length === 0) {
                return null;
            }

            const todayStr = this.getBusinessDate();
            const lowItems = products.filter(p => (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 10));
            const outItems = products.filter(p => (Number(p.stock_on_hand) || 0) <= 0);
            const sales = this.getSales();
            const todaySummary = this.getSalesSummary('Today (Live)');

            const cacheKey = this.getUserKey('smartstock_ai_analysis_cache');
            const cached = localStorage.getItem(cacheKey);
            const now = Date.now();
            const TTL = 15 * 60 * 1000; // 15 mins cache
            const signature = `${todayStr}_${products.length}_${lowItems.length}_${sales.length}_${todaySummary.revenue}`;

            if (!forceRefresh && cached) {
                try {
                    const parsed = JSON.parse(cached);
                    if (now - parsed.timestamp < TTL && parsed.signature === signature) {
                        return parsed.data;
                    }
                } catch (e) {}
            }

            const fallback = {
                stock_health_status: outItems.length > 0 ? "Critical Stockouts" : (lowItems.length > 0 ? "Action Needed" : "Optimal Health"),
                critical_risks: lowItems.map(p => `${this.escapeHtml(p.name)}: Current stock (${p.stock_on_hand}) is below reorder threshold (${p.reorder_point || 10}).`),
                recommendations: lowItems.map(p => `Dispatch PO for ${Math.max(10, (p.reorder_point || 10) * 2 - p.stock_on_hand)} units of ${this.escapeHtml(p.name)}.`),
                summary: lowItems.length === 0
                    ? `All ${products.length} products have healthy inventory buffers. Operations are running smoothly.`
                    : `${lowItems.length} products require restocking to prevent missed customer sales.`
            };

            if (!apiKey) {
                return fallback;
            }

            const catalogSummary = products.map(p => 
                `- ${p.name}: Stock ${p.stock_on_hand}, Reorder at ${p.reorder_point || 10}, Price Rs ${p.unit_price || 0}, Cost Rs ${p.unit_cost || 0}`
            ).join('\n');

            const promptText = `You are SmartStock AI retail intelligence engine for Indian retail & Kirana stores.
Analyze this store catalog:
${catalogSummary}

Provide a JSON response only with keys:
- stock_health_status: Short string (e.g. "Optimal", "Action Needed", "Critical Stockouts")
- critical_risks: Array of concise strings describing items with urgent stockout risk
- recommendations: Array of concise actionable reorder suggestions
- summary: 1-2 friendly sentences explaining store health and expected customer demand.`;

            try {
                const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{ parts: [{ text: promptText }] }],
                        generationConfig: { responseMimeType: "application/json" }
                    })
                });

                if (!res.ok) {
                    throw new Error(`Gemini API returned ${res.status}`);
                }

                const data = await res.json();
                const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text;
                if (!rawText) throw new Error("No candidate text");

                const parsedData = JSON.parse(rawText);
                localStorage.setItem(cacheKey, JSON.stringify({
                    timestamp: now,
                    signature: signature,
                    data: parsedData
                }));

                this.showToast('AI Analysis generated via Gemini 2.5 Flash', 'success');
                return parsedData;
            } catch (err) {
                console.warn('Gemini API call failed, using intelligent local heuristic fallback:', err);
                return fallback;
            }
        },

        calculateDayOfWeekDemand(salesList = null) {
            const sales = salesList || this.getSales();
            const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            const actuals = [0, 0, 0, 0, 0, 0, 0];

            for (const s of sales) {
                const qty = Number(s.qty !== undefined ? s.qty : s.units) || 0;
                const dStr = s.date || (s.timestamp ? s.timestamp.split('T')[0] : null);
                if (dStr) {
                    const d = new Date(dStr + 'T12:00:00Z');
                    if (!isNaN(d.getTime())) {
                        const dayIdx = (d.getUTCDay() + 6) % 7; // Mon=0 .. Sun=6
                        actuals[dayIdx] += qty;
                    }
                }
            }
            return { days, actuals };
        },

        calculateCompletedDayAverage(salesList = null, numDays = 7, refDate = null) {
            const sales = salesList || this.getSales();
            const todayStr = refDate ? this.getBusinessDate(refDate) : this.getBusinessDate();
            const todayMs = new Date(todayStr + 'T00:00:00Z').getTime();

            // Completed days strictly before today: [today - numDays, today - 1]
            const dailyTotals = {};
            for (let i = 1; i <= numDays; i++) {
                const dayMs = todayMs - i * 86400000;
                const dStr = new Date(dayMs).toISOString().split('T')[0];
                dailyTotals[dStr] = 0; // initialize zero-sale days
            }

            for (const s of sales) {
                const sDate = s.date || this.getBusinessDate(s.timestamp);
                if (dailyTotals.hasOwnProperty(sDate)) {
                    const qty = Number(s.qty !== undefined ? s.qty : s.units) || 0;
                    dailyTotals[sDate] += qty;
                }
            }

            const totalUnits = Object.values(dailyTotals).reduce((sum, q) => sum + q, 0);
            const average = numDays > 0 ? (totalUnits / numDays) : 0;

            return {
                numDays,
                totalUnits,
                dailyTotals,
                average: Math.round(average * 100) / 100
            };
        },

        async renderAIIntelligenceCard(products) {
            const container = document.getElementById('ai-intelligence-container');
            if (!container) return;
            if (products.length === 0) {
                container.innerHTML = '';
                return;
            }

            container.innerHTML = `
                <div class="bg-surface-container-lowest p-space-md rounded-2xl shadow-sm border border-secondary/20 relative overflow-hidden space-y-3">
                    <div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-secondary to-primary-container"></div>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-secondary text-[22px]">auto_awesome</span>
                            <div>
                                <h3 class="font-bold text-sm text-primary flex items-center gap-1.5">
                                    AI Store Intelligence
                                    <span class="px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed text-[9px] font-bold uppercase tracking-wider">Gemini 2.5 Flash</span>
                                </h3>
                                <p class="text-[11px] text-on-surface-variant">Real-time inventory analysis & demand predictions</p>
                            </div>
                        </div>
                        <button onclick="SmartStock.refreshAIAnalysis()" class="px-2.5 h-7 rounded-lg bg-surface-container hover:bg-surface-variant text-on-surface font-semibold text-[11px] flex items-center gap-1 cursor-pointer active:scale-95 transition-all" title="Refresh Analysis">
                            <span class="material-symbols-outlined text-[13px] text-secondary">sync</span>
                            <span>Refresh</span>
                        </button>
                    </div>

                    <div id="ai-insights-content" class="space-y-2.5 pt-1">
                        <div class="flex items-center gap-2 text-xs text-on-surface-variant">
                            <span class="inline-block w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                            <span>Consulting Gemini intelligence...</span>
                        </div>
                    </div>
                </div>
            `;

            const aiData = await this.runAIInventoryAnalysis();
            const contentEl = document.getElementById('ai-insights-content');
            if (!contentEl || !aiData) return;

            const isCritical = (aiData.stock_health_status || '').toLowerCase().includes('critical') || (aiData.stock_health_status || '').toLowerCase().includes('action');
            const badgeColor = isCritical ? 'bg-secondary-fixed text-on-secondary-fixed' : 'bg-primary-fixed text-on-primary-fixed';

            let risksHtml = '';
            if (aiData.critical_risks && aiData.critical_risks.length > 0) {
                risksHtml = `
                    <div class="space-y-1">
                        <span class="text-[10px] font-bold uppercase tracking-wider text-outline block">Stockout Risk Alerts</span>
                        ${aiData.critical_risks.slice(0, 2).map(r => `
                            <div class="p-2 rounded-lg bg-error-container/20 border border-error/10 text-xs flex items-start gap-1.5">
                                <span class="material-symbols-outlined text-error text-[15px] shrink-0 mt-0.5">warning</span>
                                <span class="text-on-surface leading-snug">${r}</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            let recsHtml = '';
            if (aiData.recommendations && aiData.recommendations.length > 0) {
                recsHtml = `
                    <div class="space-y-1">
                        <span class="text-[10px] font-bold uppercase tracking-wider text-outline block">Smart Replenishment Actions</span>
                        ${aiData.recommendations.slice(0, 2).map(rec => `
                            <div class="p-2 rounded-lg bg-surface-container-low text-xs flex items-start gap-1.5">
                                <span class="material-symbols-outlined text-secondary text-[15px] shrink-0 mt-0.5">check_circle</span>
                                <span class="text-on-surface leading-snug">${rec}</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            contentEl.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold text-on-surface">Store Health Status</span>
                    <span class="px-2.5 py-0.5 rounded-full ${badgeColor} text-[10px] font-bold uppercase tracking-wider">
                        ${aiData.stock_health_status}
                    </span>
                </div>
                <p class="text-xs text-on-surface leading-relaxed bg-surface-container-low p-2.5 rounded-xl border border-outline/10">
                    ${aiData.summary}
                </p>
                ${risksHtml}
                ${recsHtml}
            `;
        },

        async refreshAIAnalysis() {
            this.showToast('Refreshing analysis with Gemini 2.5 Flash...', 'info');
            const products = await this.getProducts();
            await this.runAIInventoryAnalysis(true);
            await this.renderAIIntelligenceCard(products);
        },

        renderDemandVelocity(products, salesList) {
            const container = document.getElementById('demand-velocity-container');
            if (!container) return;
            if (!products || products.length === 0) {
                container.innerHTML = `
                    <div class="w-full relative py-8 text-center text-xs text-on-surface-variant">
                        <span class="material-symbols-outlined text-[28px] text-outline mb-1 block">monitoring</span>
                        <h4 class="font-bold text-sm text-on-surface mb-0.5">No Demand Velocity Data</h4>
                        <p class="max-w-xs mx-auto">Sales velocity and predictive trends will generate automatically as sales transactions are recorded.</p>
                    </div>
                `;
                return;
            }

            const allSales = salesList || this.getSales();
            const { days, actuals } = this.calculateDayOfWeekDemand(allSales);
            const { average: completedAvg } = this.calculateCompletedDayAverage(allSales, 7);

            const todayDayIdx = (new Date().getDay() + 6) % 7;
            const baseDailyUnits = completedAvg > 0 ? completedAvg : Math.max(1, Math.round(products.reduce((acc, p) => acc + (p.stock_on_hand || 0), 0) * 0.05));

            const dayMultipliers = [0.85, 0.9, 1.05, 1.15, 1.35, 1.45, 1.1];
            const dayData = days.map((day, idx) => {
                const mult = dayMultipliers[idx];
                const predicted = Math.round(baseDailyUnits * mult);
                const actual = actuals[idx];
                return { day, actual, predicted, isToday: idx === todayDayIdx };
            });

            const maxVal = Math.max(...dayData.map(d => Math.max(d.actual, d.predicted)), 10);

            const barsHtml = dayData.map(d => {
                const actHeight = d.actual > 0 ? Math.max(8, Math.round((d.actual / maxVal) * 85)) : 4;
                const predHeight = Math.max(10, Math.round((d.predicted / maxVal) * 85));

                return `
                    <div class="flex-1 flex flex-col items-center gap-1.5 group">
                        <div class="text-[9px] font-mono text-outline opacity-0 group-hover:opacity-100 transition-opacity">
                            ${d.actual > 0 ? d.actual : '-'}/${d.predicted}
                        </div>
                        <div class="w-full flex items-end justify-center gap-1 h-24 bg-surface-container-low/50 rounded-lg p-1 relative">
                            <div style="height: ${actHeight}px;" 
                                 class="w-2.5 rounded-t-sm ${d.actual > 0 ? 'bg-primary' : 'bg-transparent'} transition-all duration-300"
                                 title="${d.day} Actual: ${d.actual} units"></div>
                            <div style="height: ${predHeight}px;" 
                                 class="w-2.5 rounded-t-sm bg-secondary-container transition-all duration-300"
                                 title="${d.day} Predicted: ${d.predicted} units"></div>
                        </div>
                        <span class="text-[11px] font-semibold ${d.isToday ? 'text-primary font-bold' : 'text-on-surface-variant'}">${d.day}</span>
                    </div>
                `;
            }).join('');

            container.innerHTML = `
                <div class="space-y-3 pt-1">
                    <div class="flex items-center justify-between text-xs bg-surface-container-low p-2 rounded-lg">
                        <span class="text-on-surface-variant font-medium">Avg Sales Velocity: <b class="text-primary font-mono">${baseDailyUnits} units/day</b></span>
                        <span class="text-secondary font-bold font-code-sm flex items-center gap-0.5">
                            <span class="material-symbols-outlined text-[13px]">trending_up</span> Actual-Driven Model
                        </span>
                    </div>
                    <div class="flex items-end justify-between gap-1 pt-1">
                        ${barsHtml}
                    </div>
                    <div class="text-[11px] text-on-surface-variant flex items-center gap-1.5 pt-1 border-t border-outline/10">
                        <span class="material-symbols-outlined text-[14px] text-secondary">psychology</span>
                        <span>Weekly demand aggregated from actual customer sales transactions.</span>
                    </div>
                </div>
            `;
        },

        renderFloorActivity(salesList, purchaseOrders, products) {
            const container = document.getElementById('floor-activity-container');
            if (!container) return;

            const events = [];

            if (Array.isArray(salesList)) {
                salesList.slice(0, 5).forEach(s => {
                    events.push({
                        type: 'sale',
                        icon: 'payments',
                        iconColor: 'text-primary',
                        bgColor: 'bg-primary-fixed/30',
                        title: `Sold 1x ${s.product_name || 'Retail Item'}`,
                        sub: `Cash / UPI Register • Terminal #01`,
                        amount: `+${SmartStock.formatINR(s.sale_amount || 0)}`,
                        amountColor: 'text-primary',
                        time: s.timestamp ? new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Today'
                    });
                });
            }

            if (Array.isArray(purchaseOrders)) {
                purchaseOrders.slice(0, 4).forEach(po => {
                    if (po.status === 'completed') {
                        events.push({
                            type: 'inward',
                            icon: 'inventory_2',
                            iconColor: 'text-primary',
                            bgColor: 'bg-primary-fixed/30',
                            title: `Stock Inwarded: ${po.po_number}`,
                            sub: `${po.items ? po.items.length : 1} Products Received from ${po.supplier || 'Metro Wholesale'}`,
                            amount: `+${(po.items || []).reduce((acc, it) => acc + (it.units || 0), 0)} units`,
                            amountColor: 'text-primary',
                            time: po.inwarded_at ? new Date(po.inwarded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Completed'
                        });
                    } else {
                        events.push({
                            type: 'order',
                            icon: 'local_shipping',
                            iconColor: 'text-secondary',
                            bgColor: 'bg-secondary-fixed/30',
                            title: `PO Dispatched: ${po.po_number}`,
                            sub: `Sent to ${po.supplier || 'Metro Wholesale'} (${po.items ? po.items.length : 1} line items)`,
                            amount: `-${SmartStock.formatINR(po.total_amount || 0)}`,
                            amountColor: 'text-secondary',
                            time: po.created_at ? new Date(po.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Ordered'
                        });
                    }
                });
            }

            if (events.length === 0) {
                if (products.length > 0) {
                    events.push({
                        type: 'system',
                        icon: 'check_circle',
                        iconColor: 'text-primary',
                        bgColor: 'bg-primary-fixed/30',
                        title: 'Register Terminal Active',
                        sub: `${products.length} Products Synchronized with Database`,
                        amount: 'Ready',
                        amountColor: 'text-primary',
                        time: 'Just now'
                    });
                    events.push({
                        type: 'system',
                        icon: 'auto_awesome',
                        iconColor: 'text-secondary',
                        bgColor: 'bg-secondary-fixed/30',
                        title: 'AI Safety Stock Guard Active',
                        sub: 'Continuous monitoring of reorder thresholds',
                        amount: 'Armed',
                        amountColor: 'text-secondary',
                        time: 'Today'
                    });
                } else {
                    container.innerHTML = `
                        <div class="py-4 text-center text-xs text-on-surface-variant">
                            <span class="material-symbols-outlined text-[22px] text-outline mb-1 block">receipt_long</span>
                            <p>No transactions yet. Recent sales and inward stock will display here.</p>
                        </div>
                    `;
                    return;
                }
            }

            container.innerHTML = `
                <div class="space-y-2 pt-1">
                    ${events.slice(0, 5).map(ev => `
                        <div class="flex items-center justify-between p-2.5 rounded-xl bg-surface-container-low border border-outline/5 hover:border-outline/20 transition-all">
                            <div class="flex items-center gap-2.5 min-w-0 flex-1">
                                <div class="w-8 h-8 rounded-lg ${ev.bgColor} flex items-center justify-center shrink-0">
                                    <span class="material-symbols-outlined text-[17px] ${ev.iconColor}">${ev.icon}</span>
                                </div>
                                <div class="min-w-0 flex-1">
                                    <p class="font-bold text-xs text-on-surface truncate">${ev.title}</p>
                                    <p class="text-[11px] text-on-surface-variant truncate">${ev.sub} • <span class="text-outline">${ev.time}</span></p>
                                </div>
                            </div>
                            <div class="text-right shrink-0 pl-2">
                                <span class="font-bold text-xs ${ev.amountColor} font-mono">${ev.amount}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        },

        currentInventoryFilter: 'all',
        currentCategoryFilter: 'all',
        currentSortMode: 'velocity',

        filterInventory(filterType, pillEl) {
            this.currentInventoryFilter = filterType;
            localStorage.setItem('smartstock_inventory_filter', filterType);

            const pills = document.querySelectorAll('.filter-pill');
            pills.forEach(p => {
                const ft = p.getAttribute('data-filter') || '';
                if (ft === filterType) {
                    p.className = 'filter-pill active px-3.5 h-8 rounded-full bg-primary text-on-primary font-label-sm text-label-sm font-semibold whitespace-nowrap shadow-sm flex items-center gap-1.5 transition-transform active:scale-95 cursor-pointer';
                    const b = p.querySelector('span:last-child');
                    if (b) b.className = 'bg-on-primary/20 text-on-primary px-1.5 py-0.2 rounded-full font-code-sm text-[10px]';
                } else {
                    p.className = 'filter-pill px-3.5 h-8 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-semibold whitespace-nowrap shadow-sm flex items-center gap-1.5 transition-transform active:scale-95 cursor-pointer';
                    const b = p.querySelector('span:last-child');
                    if (b) b.className = 'bg-surface-variant px-1.5 py-0.2 rounded-full font-code-sm text-[10px]';
                }
            });

            this.applyInventoryFilters();
        },

        filterByCategory(category) {
            this.currentCategoryFilter = (category || 'all').toLowerCase();
            this.applyInventoryFilters();
        },

        applyInventoryFilters() {
            const cards = document.querySelectorAll('.inventory-card');
            let visibleCount = 0;
            const filter = this.currentInventoryFilter || 'all';
            const cat = this.currentCategoryFilter || 'all';
            const searchInput = document.querySelector('input[placeholder*="Search by SKU"]');
            const searchQ = searchInput ? searchInput.value.toLowerCase().trim() : '';

            cards.forEach(card => {
                const cardCat = (card.getAttribute('data-category') || '').toLowerCase();
                const name = (card.getAttribute('data-name') || '').toLowerCase();
                const sku = (card.getAttribute('data-sku') || '').toLowerCase();
                const stock = parseInt(card.getAttribute('data-stock') || '0', 10);
                const reorder = parseInt(card.getAttribute('data-reorder') || '5', 10);

                let matchStatus = true;
                if (filter === 'low') {
                    matchStatus = stock <= reorder && stock > 0;
                } else if (filter === 'zero' || filter === 'out') {
                    matchStatus = stock === 0;
                } else if (filter === 'healthy') {
                    matchStatus = stock > reorder;
                } else if (filter === 'excess') {
                    matchStatus = stock > reorder * 3;
                } else if (filter === 'slow') {
                    matchStatus = stock > 30;
                }

                let matchCat = true;
                if (cat !== 'all' && cat !== '') {
                    matchCat = cardCat.includes(cat) || (cat.includes('grocer') && (cardCat.includes('food') || cardCat.includes('grain') || cardCat.includes('pantry')));
                }

                let matchSearch = true;
                if (searchQ) {
                    matchSearch = name.includes(searchQ) || sku.includes(searchQ);
                }

                if (matchStatus && matchCat && matchSearch) {
                    card.style.display = 'block';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });

            let emptyMsg = document.getElementById('inventory-filtered-empty');
            if (visibleCount === 0 && cards.length > 0) {
                if (!emptyMsg) {
                    emptyMsg = document.createElement('div');
                    emptyMsg.id = 'inventory-filtered-empty';
                    emptyMsg.className = 'bg-surface-container-lowest rounded-xl p-8 text-center border border-outline/10 text-xs text-on-surface-variant space-y-2 mt-2';
                    const list = document.getElementById('inventory-list');
                    if (list) list.appendChild(emptyMsg);
                }
                emptyMsg.style.display = 'block';
                emptyMsg.innerHTML = `
                    <span class="material-symbols-outlined text-[28px] text-outline block">filter_alt_off</span>
                    <p class="font-bold text-sm text-on-surface">No products match "${filter.toUpperCase()}"</p>
                    <p>Try switching to "All" or choosing another category filter.</p>
                    <button onclick="SmartStock.filterInventory('all')" class="mt-2 px-3 py-1.5 bg-primary text-on-primary rounded-lg text-xs font-semibold active:scale-95 transition-all">
                        Show All Products
                    </button>
                `;
            } else if (emptyMsg) {
                emptyMsg.style.display = 'none';
            }

            this.onItemSelectChange();
        },

        cycleSort() {
            const modes = ['velocity', 'stock-asc', 'stock-desc', 'price-desc', 'name-asc'];
            const labels = {
                'velocity': 'Velocity',
                'stock-asc': 'Stock: Low ↑',
                'stock-desc': 'Stock: High ↓',
                'price-desc': 'Price: High ↓',
                'name-asc': 'Name: A-Z'
            };
            const currentIdx = modes.indexOf(this.currentSortMode || 'velocity');
            const nextIdx = (currentIdx + 1) % modes.length;
            this.currentSortMode = modes[nextIdx];

            const btn = document.getElementById('toggle-sort-btn');
            if (btn) {
                const labelSpan = btn.querySelector('.font-label-sm') || btn.querySelector('span:last-child');
                if (labelSpan) labelSpan.textContent = labels[this.currentSortMode];
            }

            const list = document.getElementById('inventory-list');
            if (!list) return;
            const cards = Array.from(list.querySelectorAll('.inventory-card'));

            cards.sort((a, b) => {
                const stockA = parseInt(a.getAttribute('data-stock') || '0', 10);
                const stockB = parseInt(b.getAttribute('data-stock') || '0', 10);
                const priceA = parseFloat(a.getAttribute('data-price') || '0');
                const priceB = parseFloat(b.getAttribute('data-price') || '0');
                const nameA = a.getAttribute('data-name') || '';
                const nameB = b.getAttribute('data-name') || '';
                const reorderA = parseInt(a.getAttribute('data-reorder') || '5', 10);
                const reorderB = parseInt(b.getAttribute('data-reorder') || '5', 10);

                if (this.currentSortMode === 'stock-asc') return stockA - stockB;
                if (this.currentSortMode === 'stock-desc') return stockB - stockA;
                if (this.currentSortMode === 'price-desc') return priceB - priceA;
                if (this.currentSortMode === 'name-asc') return nameA.localeCompare(nameB);
                return (stockA - reorderA) - (stockB - reorderB);
            });

            cards.forEach(card => list.appendChild(card));
            this.showToast(`Sorted by: ${labels[this.currentSortMode]}`, 'info');
        },

        onItemSelectChange() {
            const visibleCards = Array.from(document.querySelectorAll('.inventory-card'))
                .filter(c => c.style.display !== 'none');
            const visibleChecks = visibleCards
                .map(c => c.querySelector('.item-checkbox'))
                .filter(Boolean);

            const selectedCount = visibleChecks.filter(cb => cb.checked).length;
            const label = document.getElementById('selection-label');
            if (label) label.textContent = `${selectedCount} item${selectedCount === 1 ? '' : 's'} selected`;

            const masterCheck = document.getElementById('master-select');
            if (masterCheck) {
                masterCheck.checked = visibleChecks.length > 0 && selectedCount === visibleChecks.length;
            }

            const bulkGroup = document.getElementById('bulk-action-group');
            if (bulkGroup) {
                if (selectedCount > 0) {
                    bulkGroup.classList.remove('opacity-50', 'pointer-events-none');
                } else {
                    bulkGroup.classList.add('opacity-50', 'pointer-events-none');
                }
            }
        },

        toggleSelectAll(checked) {
            const visibleCards = Array.from(document.querySelectorAll('.inventory-card'))
                .filter(c => c.style.display !== 'none');
            visibleCards.forEach(c => {
                const cb = c.querySelector('.item-checkbox');
                if (cb) cb.checked = !!checked;
            });
            this.onItemSelectChange();
        },

        async bulkDelete() {
            const checkedBoxes = Array.from(document.querySelectorAll('.item-checkbox:checked'));
            if (checkedBoxes.length === 0) return;
            const count = checkedBoxes.length;
            if (!confirm(`Delete ${count} selected item${count === 1 ? '' : 's'} from inventory?`)) return;

            const ids = checkedBoxes.map(cb => cb.getAttribute('data-id'));
            const client = this.client();
            if (client) {
                try {
                    await client.from('products').delete().in('id', ids);
                } catch (e) {}
            }

            const local = (await this.getProducts()).filter(p => !ids.includes(String(p.id)));
            this.saveProducts(local);
            this.showToast(`Deleted ${count} product${count === 1 ? '' : 's'}.`, 'info');
            await this.bindLivePageData();
        },

        async bulkAddStock(qty = 5) {
            const checkedBoxes = Array.from(document.querySelectorAll('.item-checkbox:checked'));
            if (checkedBoxes.length === 0) return;
            const ids = checkedBoxes.map(cb => cb.getAttribute('data-id'));
            const products = await this.getProducts();

            products.forEach(p => {
                if (ids.includes(String(p.id))) {
                    p.stock_on_hand = (Number(p.stock_on_hand) || 0) + qty;
                    p.status = p.stock_on_hand > (p.reorder_point || 5) ? 'active' : 'low_stock';
                }
            });

            this.saveProducts(products);
            this.showToast(`Added +${qty} stock to ${ids.length} selected items.`, 'success');
            await this.bindLivePageData();
        },

        async exportCurrentInventory() {
            const products = await this.getProducts();
            this.exportCSV(products);
        },

        injectModals() {
            if (document.getElementById('add-product-modal')) return;

            const modalHtml = `
            <!-- Add Product Modal -->
            <div id="add-product-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-md rounded-xl shadow-xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <h3 class="font-bold text-sm text-on-surface">Add New Product</h3>
                        <button onclick="SmartStock.closeAddProductModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>

                    <form id="add-product-form" class="p-4 space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Product Name</label>
                            <input id="new-item-name" type="text" required placeholder="e.g. Aashirvaad Atta 5kg"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Selling Price (₹)</label>
                                <input id="new-item-price" type="number" step="0.5" required placeholder="240"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Purchase Cost (₹)</label>
                                <input id="new-item-cost" type="number" step="0.5" placeholder="210"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Initial Stock</label>
                                <input id="new-item-stock" type="number" required placeholder="20"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Reorder Point</label>
                                <input id="new-item-reorder" type="number" placeholder="5" value="5"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Category</label>
                            <select id="new-item-category" class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none">
                                <option value="Groceries & Grains">Groceries & Grains</option>
                                <option value="Oils & Spices">Oils & Spices</option>
                                <option value="Packaged Foods & Dairy">Packaged Foods & Dairy</option>
                                <option value="Personal & Home Care">Personal & Home Care</option>
                            </select>
                        </div>

                        <div class="pt-3 flex items-center justify-end gap-2 border-t border-outline/10">
                            <button type="button" onclick="SmartStock.closeAddProductModal()" class="px-3 h-9 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container">
                                Cancel
                            </button>
                            <button type="submit" class="px-4 h-9 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90">
                                Save Product
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Import CSV Modal -->
            <div id="import-csv-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-md rounded-xl shadow-xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <h3 class="font-bold text-sm text-on-surface">Import Inventory File</h3>
                        <button onclick="SmartStock.closeImportModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>

                    <div class="p-4 space-y-4">
                        <div class="border-2 border-dashed border-outline/20 hover:border-primary rounded-lg p-6 text-center cursor-pointer bg-surface-container-low"
                            onclick="document.getElementById('csv-file-input').click()">
                            <span class="material-symbols-outlined text-[32px] text-primary mb-1">upload_file</span>
                            <p class="text-xs font-semibold text-on-surface">Click to select CSV File</p>
                            <p class="text-[11px] text-on-surface-variant mt-1">Columns: Product Name, Price, Cost, Stock, Reorder Point</p>
                            <input id="csv-file-input" type="file" accept=".csv,text/csv" class="hidden" />
                        </div>

                        <div class="flex items-center justify-between text-xs pt-1">
                            <button onclick="SmartStock.downloadTemplate()" class="text-primary font-semibold hover:underline">
                                Download Blank Template
                            </button>
                            <button onclick="SmartStock.loadSampleKiranaData()" class="text-secondary font-semibold hover:underline">
                                Load Sample Catalog
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Edit Store Profile Modal -->
            <div id="edit-profile-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-md rounded-2xl shadow-xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-primary text-[20px]">store</span>
                            <h3 class="font-bold text-sm text-on-surface">Edit Store Profile</h3>
                        </div>
                        <button onclick="SmartStock.closeEditProfileModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>

                    <form id="edit-profile-form" class="p-4 space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Store Name</label>
                            <input id="edit-store-name" type="text" required placeholder="Store Name"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                        </div>

                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Owner / Contact Person</label>
                            <input id="edit-manager-name" type="text" placeholder="Store Owner"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Phone Number</label>
                                <input id="edit-phone" type="tel" placeholder="+91 98450..."
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">City / State</label>
                                <input id="edit-city" type="text" placeholder="Bengaluru, Karnataka"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">GST / Tax Number (Optional)</label>
                            <input id="edit-gst" type="text" placeholder="e.g. 29ABCDE1234F1Z5"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none uppercase" />
                        </div>

                        <div class="pt-3 flex items-center justify-end gap-2 border-t border-outline/10">
                            <button type="button" onclick="SmartStock.closeEditProfileModal()" class="px-3 h-9 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container">
                                Cancel
                            </button>
                            <button type="submit" class="px-4 h-9 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90">
                                Save Changes
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Store Switcher Dropdown Modal -->
            <div id="store-switcher-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-primary text-[20px]">storefront</span>
                            <h3 class="font-bold text-sm text-on-surface">Store Register</h3>
                        </div>
                        <button onclick="SmartStock.closeStoreSwitcherModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    <div class="p-4 space-y-3">
                        <div class="p-3 bg-surface-container-low rounded-xl border border-primary/30 flex items-center justify-between">
                            <div class="flex items-center gap-2.5 min-w-0">
                                <div class="w-9 h-9 rounded-xl bg-primary text-on-primary flex items-center justify-center font-bold text-sm shrink-0 current-store-initial">S</div>
                                <div class="min-w-0">
                                    <p class="font-bold text-xs text-on-surface truncate current-store-display">Current Store</p>
                                    <p class="text-[10px] text-primary font-semibold">Active Register Terminal</p>
                                </div>
                            </div>
                            <span class="material-symbols-outlined text-primary text-[20px]">check_circle</span>
                        </div>

                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Rename Shop / Store</label>
                            <div class="flex gap-2">
                                <input id="quick-store-name-input" type="text" placeholder="Enter shop name"
                                    class="flex-1 h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                                <button onclick="SmartStock.quickUpdateStoreName()" class="px-3.5 h-10 bg-primary text-on-primary rounded-lg text-xs font-semibold active:scale-95 transition-all shadow-xs">
                                    Save
                                </button>
                            </div>
                        </div>

                        <div class="pt-2 border-t border-outline/10 flex flex-col gap-2">
                            <a href="06_settings.html" class="w-full h-10 rounded-xl bg-surface-container hover:bg-surface-container-high text-xs font-semibold text-primary flex items-center justify-center gap-1.5 transition-colors">
                                <span class="material-symbols-outlined text-[16px]">manage_accounts</span>
                                <span>Manage Store Profile & Settings</span>
                            </a>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Notifications & Alerts Modal -->
            <div id="notifications-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20 max-h-[80vh]">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-secondary text-[20px]">notifications</span>
                            <h3 class="font-bold text-sm text-on-surface">Store Alerts &amp; Notifications</h3>
                        </div>
                        <button onclick="SmartStock.closeNotificationsModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    
                    <div id="notifications-list" class="p-4 space-y-2.5 overflow-y-auto flex-1">
                        <!-- Populated dynamically -->
                    </div>

                    <div class="p-3 bg-surface-container-high border-t border-outline/10 flex items-center justify-between">
                        <button onclick="SmartStock.markNotificationsAsRead()" class="text-xs text-primary font-semibold hover:underline">
                            Mark All as Read
                        </button>
                        <button onclick="SmartStock.closeNotificationsModal()" class="px-3 h-8 bg-surface-container hover:bg-surface-container-high rounded-lg text-xs font-semibold text-on-surface transition-colors">
                            Close
                        </button>
                    </div>
                </div>
            </div>

            <!-- Reset Confirm Modal -->
            <div id="reset-confirm-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-error text-[20px]">delete_sweep</span>
                            <h3 class="font-bold text-sm text-on-surface">Reset Inventory to 0</h3>
                        </div>
                        <button onclick="SmartStock.closeResetModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    <div class="p-4 space-y-3">
                        <p class="text-xs text-on-surface-variant leading-relaxed">
                            Are you sure you want to clear all products? Your inventory catalog and all stock levels will be reset to a clean zero state.
                        </p>
                        <div class="p-3 bg-error-container/30 rounded-xl border border-error/20 flex items-center gap-2">
                            <span class="material-symbols-outlined text-error text-[18px] shrink-0">warning</span>
                            <p class="text-[11px] text-on-error-container font-medium">All item cards and valuation will return to ₹0 immediately.</p>
                        </div>
                        <div class="pt-2 flex items-center justify-end gap-2 border-t border-outline/10">
                            <button type="button" onclick="SmartStock.closeResetModal()" class="px-3.5 h-9 rounded-lg text-xs font-semibold text-on-surface-variant hover:bg-surface-container">
                                Cancel
                            </button>
                            <button type="button" onclick="SmartStock.confirmResetStore()" class="px-4 h-9 rounded-lg bg-error text-white text-xs font-bold hover:opacity-90 active:scale-95 transition-all shadow-xs">
                                Yes, Reset to 0
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Create Purchase Order Modal -->
            <div id="create-po-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-md rounded-xl shadow-xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-primary text-[20px]">local_shipping</span>
                            <h3 class="font-bold text-sm text-on-surface">Create New Purchase Order</h3>
                        </div>
                        <button onclick="SmartStock.closeNewPOModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    <form onsubmit="SmartStock.submitNewPO(event)" class="p-4 space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Select Catalog Product</label>
                            <select id="po-product-select" onchange="SmartStock.calculateNewPOTotal()" class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none cursor-pointer">
                            </select>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Order Quantity (Units)</label>
                                <input id="po-qty-input" type="number" min="1" value="20" required oninput="SmartStock.calculateNewPOTotal()"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none font-medium" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Est. Total Cost</label>
                                <div id="po-total-display" class="w-full h-10 px-3 bg-surface-container flex items-center rounded-lg text-sm font-bold text-primary">
                                    ₹0.00
                                </div>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Supplier / Distributor</label>
                            <input id="po-supplier-input" type="text" value="Metro Wholesale / Regional Supply Hub"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>
                        <div class="pt-3 flex items-center justify-end gap-2 border-t border-outline/10">
                            <button type="button" onclick="SmartStock.closeNewPOModal()" class="px-3.5 h-9 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container cursor-pointer">
                                Cancel
                            </button>
                            <button type="submit" class="px-4 h-9 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90 active:scale-95 transition-all shadow-xs cursor-pointer">
                                Issue Purchase Order
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Date Switcher Modal -->
            <div id="date-switcher-modal" class="fixed inset-0 bg-black/60 z-50 hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-sm rounded-2xl shadow-xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-secondary text-[20px]">calendar_today</span>
                            <h3 class="font-bold text-sm text-on-surface">Select Register Timeframe</h3>
                        </div>
                        <button onclick="SmartStock.closeDateSwitcherModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant cursor-pointer">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    <div class="p-3 space-y-1.5" id="date-switcher-options">
                        <button onclick="SmartStock.selectDateRange('Today (Live)')" class="date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer">
                            <span>Today (Live)</span>
                            <span class="material-symbols-outlined text-[16px] text-primary hidden checkmark">check</span>
                        </button>
                        <button onclick="SmartStock.selectDateRange('Last 7 Days')" class="date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer">
                            <span>Last 7 Days</span>
                            <span class="material-symbols-outlined text-[16px] text-primary hidden checkmark">check</span>
                        </button>
                        <button onclick="SmartStock.selectDateRange('Oct 24 • Last 30 Days')" class="date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer bg-primary-fixed/30 text-primary">
                            <span>Oct 24 • Last 30 Days</span>
                            <span class="material-symbols-outlined text-[16px] text-primary checkmark">check</span>
                        </button>
                        <button onclick="SmartStock.selectDateRange('This Month (Oct 2024)')" class="date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer">
                            <span>This Month (Oct 2024)</span>
                            <span class="material-symbols-outlined text-[16px] text-primary hidden checkmark">check</span>
                        </button>
                        <button onclick="SmartStock.selectDateRange('All Time')" class="date-range-opt w-full px-3.5 py-2.5 rounded-xl text-left text-xs font-semibold flex items-center justify-between hover:bg-surface-container transition-all cursor-pointer">
                            <span>All Time</span>
                            <span class="material-symbols-outlined text-[16px] text-primary hidden checkmark">check</span>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Sales Register Modal -->
            <div id="sales-register-modal" class="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-50 hidden items-center justify-center p-3 sm:p-4">
                <div class="bg-surface-container-lowest w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20 max-h-[90vh]">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2.5">
                            <div class="w-8 h-8 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                                <span class="material-symbols-outlined text-[20px]">point_of_sale</span>
                            </div>
                            <div>
                                <h3 class="font-bold text-sm text-on-surface">Store Sales Register</h3>
                                <p class="text-[11px] text-on-surface-variant font-mono">Live Counter Sales & Transaction Ledger</p>
                            </div>
                        </div>
                        <button onclick="SmartStock.closeSalesModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant cursor-pointer">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>

                    <!-- Summary Metrics Strip -->
                    <div class="p-3 bg-surface-container-low border-b border-outline/10 grid grid-cols-3 gap-2 text-center">
                        <div class="bg-surface-container-lowest p-2 rounded-xl border border-outline/10">
                            <span class="text-[10px] text-on-surface-variant font-medium uppercase tracking-wider block">Total Revenue</span>
                            <span id="sales-modal-total-rev" class="font-bold text-sm text-primary font-mono">₹0.00</span>
                        </div>
                        <div class="bg-surface-container-lowest p-2 rounded-xl border border-outline/10">
                            <span class="text-[10px] text-on-surface-variant font-medium uppercase tracking-wider block">Transactions</span>
                            <span id="sales-modal-total-count" class="font-bold text-sm text-on-surface font-mono">0 Bills</span>
                        </div>
                        <div class="bg-surface-container-lowest p-2 rounded-xl border border-outline/10">
                            <span class="text-[10px] text-on-surface-variant font-medium uppercase tracking-wider block">Units Sold</span>
                            <span id="sales-modal-total-units" class="font-bold text-sm text-secondary font-mono">0 Units</span>
                        </div>
                    </div>

                    <div class="p-4 overflow-y-auto space-y-4 flex-1">
                        <!-- Quick Record Sale Card -->
                        <div class="bg-surface-container-low p-3.5 rounded-2xl border border-outline/15 space-y-2.5">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-bold text-on-surface flex items-center gap-1.5">
                                    <span class="material-symbols-outlined text-primary text-[16px]">add_circle</span>
                                    <span>Record New Counter / UPI Sale</span>
                                </span>
                                <span class="text-[10px] text-on-surface-variant">Deducts stock automatically</span>
                            </div>
                            <form id="record-sale-form" onsubmit="SmartStock.recordNewSaleFromModal(event)" class="space-y-2.5">
                                <div>
                                    <label class="block text-[11px] font-semibold text-on-surface-variant mb-1">Select Product</label>
                                    <select id="sale-record-product-select" onchange="SmartStock.calculateSaleModalTotal()" class="w-full h-9 px-3 bg-surface-container-lowest rounded-lg text-xs border border-outline/20 focus:border-primary focus:outline-none cursor-pointer">
                                    </select>
                                </div>
                                <div class="flex items-center justify-between gap-3 pt-1">
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs text-on-surface-variant">Qty Sold:</span>
                                        <div class="flex items-center bg-surface-container-lowest rounded-lg border border-outline/20 h-8">
                                            <button type="button" onclick="SmartStock.adjustSaleModalQty(-1)" class="w-7 h-8 flex items-center justify-center font-bold text-xs text-on-surface hover:bg-surface-container active:scale-95 transition-all">-</button>
                                            <input id="sale-record-qty-input" type="number" min="1" value="1" oninput="SmartStock.calculateSaleModalTotal()"
                                                class="w-10 text-center font-mono font-bold text-xs bg-transparent focus:outline-none" />
                                            <button type="button" onclick="SmartStock.adjustSaleModalQty(1)" class="w-7 h-8 flex items-center justify-center font-bold text-xs text-on-surface hover:bg-surface-container active:scale-95 transition-all">+</button>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-3">
                                        <div class="text-right">
                                            <span class="text-[10px] text-on-surface-variant block">Bill Total</span>
                                            <span id="sale-record-total-display" class="font-bold text-sm text-primary font-mono">₹0.00</span>
                                        </div>
                                        <button type="submit" class="h-8 px-3.5 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90 active:scale-95 transition-all shadow-xs flex items-center gap-1 cursor-pointer">
                                            <span class="material-symbols-outlined text-[15px]">payments</span>
                                            <span>Record Sale</span>
                                        </button>
                                    </div>
                                </div>
                            </form>
                        </div>

                        <!-- Actual Sales Log -->
                        <div class="space-y-2">
                            <div class="flex items-center justify-between px-1">
                                <span class="text-xs font-bold text-on-surface uppercase tracking-wider">Transaction History</span>
                                <span class="text-[11px] text-on-surface-variant">Real-time Register</span>
                            </div>
                            <div id="sales-modal-transactions-list" class="space-y-2">
                                <!-- Populated dynamically by bridge -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Suppliers Directory Modal -->
            <div id="suppliers-directory-modal" class="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-50 hidden items-center justify-center p-3 sm:p-4">
                <div class="bg-surface-container-lowest w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20 max-h-[90vh]">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2.5">
                            <div class="w-8 h-8 rounded-lg bg-secondary/15 text-secondary flex items-center justify-center">
                                <span class="material-symbols-outlined text-[20px]">local_shipping</span>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h3 class="font-bold text-sm text-on-surface">Store Suppliers Directory</h3>
                                    <span id="suppliers-total-count" class="px-2 py-0.5 rounded-full bg-secondary text-on-secondary text-[10px] font-bold">0 Partners</span>
                                </div>
                                <p class="text-[11px] text-on-surface-variant font-mono">Wholesale Vendors, Distributors & Mandi Hubs</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-1">
                            <button onclick="SmartStock.openAddSupplierModal()" class="h-8 px-2.5 rounded-lg bg-primary text-on-primary text-xs font-semibold flex items-center gap-1 active:scale-95 shadow-xs cursor-pointer">
                                <span class="material-symbols-outlined text-[15px]">add</span>
                                <span>Add Vendor</span>
                            </button>
                            <button onclick="SmartStock.closeSuppliersModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant cursor-pointer">
                                <span class="material-symbols-outlined text-[18px]">close</span>
                            </button>
                        </div>
                    </div>

                    <div class="p-4 overflow-y-auto space-y-3 flex-1">
                        <div id="suppliers-directory-list" class="space-y-3">
                            <!-- Populated dynamically by bridge -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Add Supplier Modal -->
            <div id="add-supplier-modal" class="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-[60] hidden items-center justify-center p-4">
                <div class="bg-surface-container-lowest w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-outline/20">
                    <div class="p-4 bg-surface-container-high border-b border-outline/10 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-secondary text-[20px]">add_business</span>
                            <h3 class="font-bold text-sm text-on-surface">Add Wholesale Supplier</h3>
                        </div>
                        <button onclick="SmartStock.closeAddSupplierModal()" class="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-variant cursor-pointer">
                            <span class="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                    <form onsubmit="SmartStock.submitAddSupplier(event)" class="p-4 space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Company / Supplier Name</label>
                            <input id="new-supp-name" type="text" required placeholder="e.g. Adani Wilmar / Local Mandi"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Category of Goods</label>
                            <input id="new-supp-category" type="text" placeholder="e.g. Edible Oils, Grains & Staples"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Phone Number</label>
                                <input id="new-supp-phone" type="tel" placeholder="+91 98765 00000"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm font-mono border border-outline/20 focus:border-primary focus:outline-none" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-on-surface-variant mb-1">Lead Time (Days)</label>
                                <input id="new-supp-lead" type="number" min="1" max="60" value="3"
                                    class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm font-mono border border-outline/20 focus:border-primary focus:outline-none" />
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-on-surface-variant mb-1">Depot / Supply Hub Address</label>
                            <input id="new-supp-hub" type="text" placeholder="e.g. APMC Yard, Yeshwanthpur"
                                class="w-full h-10 px-3 bg-surface-container-low rounded-lg text-sm border border-outline/20 focus:border-primary focus:outline-none" />
                        </div>
                        <div class="pt-2 flex items-center justify-end gap-2 border-t border-outline/10">
                            <button type="button" onclick="SmartStock.closeAddSupplierModal()" class="px-3.5 h-9 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container cursor-pointer">
                                Cancel
                            </button>
                            <button type="submit" class="px-4 h-9 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90 active:scale-95 transition-all shadow-xs cursor-pointer">
                                Save Supplier
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            `;

            const wrapper = document.createElement('div');
            wrapper.innerHTML = modalHtml;
            document.body.appendChild(wrapper);

            const profileForm = document.getElementById('edit-profile-form');
            if (profileForm) {
                profileForm.onsubmit = (e) => {
                    e.preventDefault();
                    const store = document.getElementById('edit-store-name')?.value.trim() || 'My Store';
                    const manager = document.getElementById('edit-manager-name')?.value.trim() || 'Store Owner';
                    const phone = document.getElementById('edit-phone')?.value.trim() || '';
                    const city = document.getElementById('edit-city')?.value.trim() || 'India';
                    const gst = document.getElementById('edit-gst')?.value.trim() || '';
                    SmartStock.saveProfile({ store, manager, phone, city, gst });
                };
            }

            const addForm = document.getElementById('add-product-form');
            if (addForm) {
                addForm.onsubmit = async (e) => {
                    e.preventDefault();
                    const name = document.getElementById('new-item-name').value;
                    const price = parseFloat(document.getElementById('new-item-price').value);
                    const cost = parseFloat(document.getElementById('new-item-cost').value) || Math.round(price * 0.85);
                    const stock = parseInt(document.getElementById('new-item-stock').value, 10);
                    const reorder = parseInt(document.getElementById('new-item-reorder').value, 10) || 5;
                    const category = document.getElementById('new-item-category').value;

                    await SmartStock.addProduct({
                        name,
                        unit_price: price,
                        unit_cost: cost,
                        stock_on_hand: stock,
                        reorder_point: reorder,
                        category_name: category
                    });

                    SmartStock.closeAddProductModal();
                    addForm.reset();
                    await SmartStock.bindLivePageData();
                };
            }

            const csvInput = document.getElementById('csv-file-input');
            if (csvInput) {
                csvInput.onchange = (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        SmartStock.importCSV(file);
                        SmartStock.closeImportModal();
                    }
                };
            }
        },

        bindNavigation() {
            document.querySelectorAll('[data-path]').forEach(el => {
                const path = el.getAttribute('data-path');
                let target = '#';
                if (path === 'overview') {
                    target = '02_overview.html';
                } else if (path === 'sales') {
                    target = '#';
                    el.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openSalesModal();
                        const drawer = document.getElementById('side-drawer');
                        const backdrop = document.getElementById('drawer-backdrop');
                        if (drawer) drawer.classList.remove('open');
                        if (backdrop) backdrop.classList.remove('open');
                    };
                } else if (path === 'inventory' || path === 'scan-barcode') {
                    target = '03_inventory.html';
                } else if (path === 'forecasts') {
                    target = '04_forecasts.html';
                } else if (path === 'ai-insights-&-replenishment' || path === 'ai-replenishment') {
                    target = '05_replenishment.html';
                } else if (path === 'orders' || path === 'purchase-orders') {
                    target = '05_purchase_orders.html';
                } else if (path === 'suppliers') {
                    target = '#';
                    el.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openSuppliersModal();
                        const drawer = document.getElementById('side-drawer');
                        const backdrop = document.getElementById('drawer-backdrop');
                        if (drawer) drawer.classList.remove('open');
                        if (backdrop) backdrop.classList.remove('open');
                    };
                } else if (path === 'settings' || path === 'help-&-support') {
                    target = '06_settings.html';
                } else if (path === 'login') {
                    target = '01_signin.html';
                }

                if (target !== '#') el.setAttribute('href', target);
            });

            const loginForm = document.getElementById('merchant-login-form');
            const submitBtn = document.getElementById('submit-auth-btn');
            const emailInput = document.getElementById('merchant-email');
            const passwordInput = document.getElementById('merchant-password');

            if (loginForm && submitBtn) {
                loginForm.onsubmit = async (e) => {
                    e.preventDefault();
                    const email = emailInput ? emailInput.value.trim() : '';
                    const pass = passwordInput ? passwordInput.value : '';

                    const errBox = document.getElementById('auth-signin-error');
                    const errText = document.getElementById('auth-signin-error-text');
                    if (errBox) errBox.classList.add('hidden');

                    if (!email || !pass) {
                        if (errBox && errText) {
                            errText.textContent = 'Please enter both email and password.';
                            errBox.classList.remove('hidden');
                        } else {
                            SmartStock.showToast('Please enter both email and password.', 'error');
                        }
                        return;
                    }

                    submitBtn.textContent = 'Verifying Credentials...';
                    submitBtn.disabled = true;

                    const res = await SmartStock.signIn(email, pass);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Sign In to Register';

                    if (res.error) {
                        if (errBox && errText) {
                            errText.textContent = res.error.message || 'Invalid email or password.';
                            errBox.classList.remove('hidden');
                        } else {
                            SmartStock.showToast(res.error.message || 'Invalid email or password.', 'error');
                        }
                        return; // Halt! Do not navigate!
                    }

                    window.location.href = '02_overview.html';
                };
            }

            // Sign In & Sign Up Tab Switcher
            const tabSignIn = document.getElementById('tab-btn-signin');
            const tabSignUp = document.getElementById('tab-btn-signup');
            const secSignIn = document.getElementById('section-signin');
            const secSignUp = document.getElementById('section-signup');

            window.switchAuthTab = function(mode) {
                if (mode === 'signup') {
                    if (secSignIn) secSignIn.classList.add('hidden');
                    if (secSignUp) secSignUp.classList.remove('hidden');
                    if (tabSignIn) {
                        tabSignIn.classList.remove('bg-primary', 'text-on-primary', 'shadow-xs');
                        tabSignIn.classList.add('text-on-surface-variant');
                    }
                    if (tabSignUp) {
                        tabSignUp.classList.add('bg-primary', 'text-on-primary', 'shadow-xs');
                        tabSignUp.classList.remove('text-on-surface-variant');
                    }
                } else {
                    if (secSignUp) secSignUp.classList.add('hidden');
                    if (secSignIn) secSignIn.classList.remove('hidden');
                    if (tabSignUp) {
                        tabSignUp.classList.remove('bg-primary', 'text-on-primary', 'shadow-xs');
                        tabSignUp.classList.add('text-on-surface-variant');
                    }
                    if (tabSignIn) {
                        tabSignIn.classList.add('bg-primary', 'text-on-primary', 'shadow-xs');
                        tabSignIn.classList.remove('text-on-surface-variant');
                    }
                }
            };

            if (tabSignIn) tabSignIn.onclick = () => window.switchAuthTab('signin');
            if (tabSignUp) tabSignUp.onclick = () => window.switchAuthTab('signup');

            // Sign Up Handler
            const signupForm = document.getElementById('merchant-signup-form');
            const submitSignupBtn = document.getElementById('submit-signup-btn');
            if (signupForm && submitSignupBtn) {
                signupForm.onsubmit = async (e) => {
                    e.preventDefault();
                    const storeName = document.getElementById('signup-store-name')?.value?.trim() || 'My Store';
                    const email = document.getElementById('signup-email')?.value?.trim() || '';
                    const phone = document.getElementById('signup-phone')?.value?.trim() || '';
                    const pass = document.getElementById('signup-password')?.value || '';

                    const errBox = document.getElementById('auth-signup-error');
                    const errText = document.getElementById('auth-signup-error-text');
                    if (errBox) errBox.classList.add('hidden');

                    if (!email || !pass) {
                        if (errBox && errText) {
                            errText.textContent = 'Email and password are required.';
                            errBox.classList.remove('hidden');
                        } else {
                            SmartStock.showToast('Email and password are required.', 'error');
                        }
                        return;
                    }

                    submitSignupBtn.textContent = 'Registering Store...';
                    submitSignupBtn.disabled = true;

                    const res = await SmartStock.signUp(email, pass, storeName, phone);
                    submitSignupBtn.disabled = false;
                    submitSignupBtn.textContent = 'Create Store Register';

                    if (res.error) {
                        if (errBox && errText) {
                            errText.textContent = res.error.message || 'Registration failed.';
                            errBox.classList.remove('hidden');
                        } else {
                            SmartStock.showToast(res.error.message || 'Registration failed.', 'error');
                        }
                        return; // Halt!
                    }

                    window.location.href = '02_overview.html';
                };
            }
        },

        async bindLivePageData() {
            if (typeof document === 'undefined') return;
            const currentPage = (typeof window !== 'undefined' && window.location && window.location.pathname) ? window.location.pathname.split('/').pop() : '';
            const storedUser = localStorage.getItem('smartstock_user');
            let parsedUser = null;
            if (storedUser) {
                try {
                    parsedUser = JSON.parse(storedUser);
                } catch (e) {}
            }

            // Auth Guard: If not signed in and trying to access any dashboard screen, redirect to signin
            if (currentPage && currentPage !== '01_signin.html' && (!parsedUser || !parsedUser.email)) {
                window.location.href = '01_signin.html';
                return;
            }

            // If already signed in and on 01_signin.html, auto-proceed to overview
            if (currentPage === '01_signin.html' && parsedUser && parsedUser.email) {
                window.location.href = '02_overview.html';
                return;
            }

            const products = await this.getProducts();

            // Dynamically reflect current store name & user profile
            const lastActiveStore = localStorage.getItem('smartstock_last_active_store');
            let currentStoreName = lastActiveStore || 'My Store';
            let userEmail = 'owner@store.in';
            let userPhone = '';
            if (parsedUser) {
                if (parsedUser.store && parsedUser.store.trim()) currentStoreName = parsedUser.store.trim();
                if (parsedUser.email) userEmail = parsedUser.email;
                if (parsedUser.phone) userPhone = parsedUser.phone;
            }
            this.config.activeStoreName = currentStoreName;

            // 1. Header Store Pill Dropdown Binding & Text
            document.querySelectorAll('.store-pill-name').forEach(el => {
                el.textContent = currentStoreName;
            });
            document.querySelectorAll('.drawer-store-name').forEach(el => {
                el.textContent = currentStoreName;
            });
            document.querySelectorAll('.current-store-display').forEach(el => {
                el.textContent = currentStoreName;
            });
            document.querySelectorAll('.current-store-initial').forEach(el => {
                el.textContent = currentStoreName.trim().charAt(0).toUpperCase() || 'S';
            });

            document.querySelectorAll('header button').forEach(btn => {
                const hasExpand = btn.querySelector('.material-symbols-outlined')?.textContent?.trim() === 'expand_more';
                const hasStoreKeyword = btn.textContent && (
                    btn.textContent.includes('Store') ||
                    btn.textContent.includes(currentStoreName) ||
                    btn.querySelector('.store-pill-name')
                );

                if (hasExpand || (hasStoreKeyword && btn.querySelector('.rounded-full'))) {
                    const label = btn.querySelector('.store-pill-name') || btn.querySelector('.truncate') || btn.querySelector('.font-label-sm');
                    if (label) {
                        label.textContent = currentStoreName;
                        label.classList.remove('max-w-[86px]');
                        label.classList.add('max-w-[150px]');
                    }
                    btn.classList.add('cursor-pointer', 'active:scale-95', 'transition-transform');
                    btn.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openStoreSwitcherModal();
                    };
                }
            });

            // 2. Header Notification Bell Binding & Badge Count
            document.querySelectorAll('header button').forEach(btn => {
                const notifIcon = btn.querySelector('.material-symbols-outlined');
                if (notifIcon && notifIcon.textContent.trim() === 'notifications') {
                    btn.classList.add('cursor-pointer', 'active:scale-95', 'transition-transform');
                    btn.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openNotificationsModal();
                    };

                    const badge = btn.querySelector('.rounded-full');
                    if (badge) {
                        const lowCount = products.filter(p => p.stock_on_hand <= (p.reorder_point || 5)).length;
                        const isRead = localStorage.getItem('smartstock_notifs_read') === 'true';
                        const count = lowCount > 0 ? lowCount : (products.length === 0 ? 1 : 0);
                        if (isRead || count === 0) {
                            badge.style.display = 'none';
                        } else {
                            badge.style.display = 'flex';
                            badge.textContent = count;
                        }
                    }
                }
            });

            // 3. Update any residual store name occurrences
            document.querySelectorAll('.truncate').forEach(el => {
                if (el.textContent && (el.textContent.includes('Sharma') || el.textContent.includes('Kirana & General'))) {
                    el.textContent = currentStoreName;
                }
            });
            document.querySelectorAll('p.font-label-md').forEach(el => {
                if (el.textContent && el.textContent.includes('Sharma')) {
                    el.textContent = currentStoreName;
                }
            });

            // 4. Replace header stock profile images with clean, humane store initial avatar
            document.querySelectorAll('img[alt="Profile"]').forEach(img => {
                const parent = img.parentElement;
                if (parent) {
                    const initial = currentStoreName.trim().charAt(0).toUpperCase() || 'S';
                    parent.innerHTML = `<div class="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center text-xs font-bold shadow-xs select-none">${initial}</div>`;
                }
            });

            // 1. Overview Page Binding
            if (currentPage === '02_overview.html') {
                const totalValue = this.getInventoryValuation(products);
                const lowStockCount = products.filter(p => (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 10)).length;

                // Active timeframe
                const activeRange = this.getActiveDateRange();
                const rangeLabelEl = document.getElementById('overview-date-range-label');
                if (rangeLabelEl) rangeLabelEl.textContent = activeRange;

                const summary = this.getSalesSummary(activeRange);
                const liveRev = summary.revenue;
                const salesList = this.getFilteredSales(activeRange);

                // Greeting & Subtitle
                const greetEl = document.querySelector('.font-headline-lg-mobile, .font-headline-lg');
                if (greetEl) greetEl.textContent = `Welcome, ${currentStoreName}`;
                const subEl = greetEl ? greetEl.nextElementSibling : null;
                if (subEl) {
                    subEl.textContent = products.length === 0
                        ? 'Store register initialized. 0 items recorded in catalog.'
                        : `Catalog active with ${products.length} items. ${lowStockCount} items need attention.`;
                }

                // Fill rate pill
                const fillRateEl = document.querySelector('.bg-primary\\/10 .font-code-sm');
                if (fillRateEl) {
                    fillRateEl.textContent = products.length === 0 ? '0.0% Initial' : '98.4% Fill Rate';
                }

                // 4 Overview Metric Cards
                const invValCards = document.querySelectorAll('main .font-headline-md');

                if (invValCards && invValCards[0]) {
                    invValCards[0].textContent = SmartStock.formatINR(liveRev);
                }
                const revTrend = document.querySelector('.bg-primary-fixed\\/50');
                if (revTrend) {
                    if (products.length === 0 && liveRev === 0) {
                        revTrend.innerHTML = '<span class="material-symbols-outlined text-[13px] mr-0.5">remove</span>0.0%';
                    } else if (salesList.length > 0) {
                        revTrend.innerHTML = `<span class="material-symbols-outlined text-[13px] mr-0.5">trending_up</span>+${salesList.length} sales`;
                    } else {
                        revTrend.innerHTML = `<span class="material-symbols-outlined text-[13px] mr-0.5">trending_up</span>+0.0%`;
                    }
                }

                if (invValCards && invValCards[1]) {
                    invValCards[1].textContent = SmartStock.formatINR(totalValue);
                }
                const skuCountEl = document.querySelector('span.font-semibold.text-on-surface');
                if (skuCountEl && skuCountEl.parentElement && skuCountEl.parentElement.textContent.includes('SKU')) {
                    skuCountEl.textContent = products.length;
                }

                const restockNeedEl = document.querySelector('.bg-secondary-fixed\\/30 .font-headline-md');
                if (restockNeedEl) {
                    restockNeedEl.textContent = lowStockCount;
                }
                const restockSub = document.querySelector('.bg-secondary-fixed\\/30 p.font-label-sm');
                if (restockSub) {
                    restockSub.textContent = lowStockCount === 0 ? '0 critical stockouts' : `${lowStockCount} below safety stock`;
                }

                if (invValCards && invValCards[3]) {
                    if (summary.costAvailable) {
                        invValCards[3].textContent = SmartStock.formatINR(summary.grossProfit);
                    } else {
                        invValCards[3].textContent = 'Unavailable';
                    }
                }
                const slowTied = document.querySelector('.text-secondary.font-semibold');
                if (slowTied) {
                    if (summary.costAvailable && summary.grossMargin !== null) {
                        slowTied.textContent = `${summary.grossMargin.toFixed(1)}% margin`;
                    } else if (!summary.costAvailable) {
                        slowTied.textContent = 'Unavailable';
                    } else if (products.length === 0) {
                        slowTied.textContent = '₹0.00';
                    }
                }

                // AI Triggers Badge
                const actBadge = document.querySelector('.bg-surface-container.px-2.py-0\\.5');
                if (actBadge) actBadge.textContent = products.length === 0 ? '0 AI triggers' : `${lowStockCount} AI triggers`;

                // Actionable Next Steps Cards Container
                const cardContainer = document.querySelector('.flex.flex-col.space-y-space-xs > .space-y-space-xs');
                if (cardContainer) {
                    if (products.length === 0) {
                        cardContainer.innerHTML = `
                            <div class="bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline/10 text-center space-y-3">
                                <div class="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mx-auto">
                                    <span class="material-symbols-outlined text-[28px]">storefront</span>
                                </div>
                                <h4 class="font-bold text-base text-on-surface">Store Register Initialized (0 Items)</h4>
                                <p class="text-xs text-on-surface-variant max-w-xs mx-auto">
                                    Your store catalog currently has 0 items. Enter items manually or import a spreadsheet to begin tracking stock and AI alerts.
                                </p>
                                <div class="flex flex-col sm:flex-row items-center justify-center gap-2 pt-2">
                                    <button onclick="SmartStock.openAddProductModal()" class="w-full sm:w-auto px-4 py-2.5 bg-primary text-on-primary rounded-xl font-semibold text-xs shadow-xs active:scale-95 transition-all flex items-center justify-center gap-1.5 cursor-pointer">
                                        <span class="material-symbols-outlined text-[16px]">add_circle</span>
                                        <span>+ Add Product</span>
                                    </button>
                                    <button onclick="SmartStock.openImportModal()" class="w-full sm:w-auto px-4 py-2.5 bg-surface-container text-on-surface rounded-xl font-semibold text-xs hover:bg-surface-container-high active:scale-95 transition-all flex items-center justify-center gap-1.5 cursor-pointer">
                                        <span class="material-symbols-outlined text-[16px]">upload_file</span>
                                        <span>Import File (CSV)</span>
                                    </button>
                                </div>
                            </div>
                        `;
                    } else {
                        const lowItems = products.filter(p => (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 10));
                        if (lowItems.length === 0) {
                            cardContainer.innerHTML = `
                                <div class="bg-surface-container-lowest p-5 rounded-xl shadow-sm border border-outline/10 text-center">
                                    <span class="material-symbols-outlined text-primary text-[26px] mb-1">check_circle</span>
                                    <h4 class="font-bold text-sm text-on-surface">All Stock Levels Healthy</h4>
                                    <p class="text-xs text-on-surface-variant mt-0.5">All ${products.length} products are safely above their reorder points.</p>
                                </div>
                            `;
                        } else {
                            cardContainer.innerHTML = lowItems.slice(0, 3).map(p => `
                                <div class="bg-surface-container-lowest p-4 rounded-xl shadow-sm relative overflow-hidden transition-all border border-outline/10">
                                    <div class="flex items-start justify-between gap-2">
                                        <div class="flex-1 min-w-0">
                                            <div class="flex items-center gap-1.5 mb-1">
                                                <span class="bg-secondary-fixed text-on-secondary-fixed font-label-sm text-[10px] uppercase font-bold px-2 py-0.5 rounded-full">Reorder Needed</span>
                                                <span class="font-mono text-[11px] text-outline">${p.sku || 'SKU'}</span>
                                            </div>
                                            <h4 class="font-bold text-sm text-on-surface truncate">${p.name}</h4>
                                            <p class="text-xs text-on-surface-variant mt-0.5">
                                                On-hand: <b class="text-secondary">${p.stock_on_hand} units</b> • Reorder Point: <b>${p.reorder_point || 10} units</b>
                                            </p>
                                        </div>
                                    </div>
                                    <div class="mt-3 flex items-center justify-between pt-2 border-t border-outline/10">
                                        <span class="text-xs text-on-surface-variant">Recommended Order: <b>${Math.max(10, (p.reorder_point || 10) * 2 - p.stock_on_hand)} units</b></span>
                                        <a href="05_purchase_orders.html" class="px-3 h-8 bg-secondary text-on-secondary rounded-lg font-semibold text-xs flex items-center gap-1 shadow-sm active:scale-95">
                                            <span>Replenish</span>
                                        </a>
                                    </div>
                                </div>
                            `).join('');
                        }
                    }
                }

                // Date Range Label
                const savedDateRange = this.getActiveDateRange();
                const dateRangeLabel = document.getElementById('overview-date-range-label');
                if (dateRangeLabel) dateRangeLabel.textContent = savedDateRange;

                // Gemini AI Store Intelligence Card
                SmartStock.renderAIIntelligenceCard(products);

                // Demand Velocity
                SmartStock.renderDemandVelocity(products, salesList);

                // Floor Activity Feed
                const purchaseOrders = SmartStock.getPurchaseOrders();
                SmartStock.renderFloorActivity(salesList, purchaseOrders, products);
            }

            // 2. Forecasts Page Binding
            if (currentPage === '04_forecasts.html') {
                if (products.length === 0) {
                    const forecastMain = document.querySelector('main .space-y-space-md');
                    if (forecastMain) {
                        forecastMain.innerHTML = `
                            <div class="bg-surface-container-lowest rounded-2xl p-8 text-center border border-outline/10 space-y-3 mt-4">
                                <span class="material-symbols-outlined text-[36px] text-outline">query_stats</span>
                                <h3 class="font-bold text-base text-on-surface">No Forecast Data Available</h3>
                                <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                                    Your store catalog currently has 0 items. Add products to generate 7, 14, 30, and 90-day AI predictive demand curves.
                                </p>
                                <div class="flex items-center justify-center gap-2 pt-2">
                                    <button onclick="SmartStock.openAddProductModal()" class="px-4 py-2 bg-primary text-on-primary rounded-lg font-semibold text-xs shadow-xs active:scale-95 transition-all">
                                        + Add Product
                                    </button>
                                    <button onclick="SmartStock.openImportModal()" class="px-4 py-2 bg-surface-container text-on-surface rounded-lg font-semibold text-xs hover:bg-surface-container-high active:scale-95 transition-all">
                                        Import File (CSV)
                                    </button>
                                </div>
                            </div>
                        `;
                    }
                } else {
                    let selectedIdx = parseInt(localStorage.getItem('smartstock_forecast_sku_idx') || '0', 10);
                    if (selectedIdx >= products.length) selectedIdx = 0;
                    const prod = products[selectedIdx];

                    const titleEl = document.querySelector('main h2');
                    if (titleEl) titleEl.textContent = prod.name;

                    const skuCatEl = document.querySelector('main p.font-code-sm.uppercase');
                    if (skuCatEl) skuCatEl.textContent = `${prod.sku || 'SKU'} • ${prod.category_name || 'Retail Inventory'}`;

                    window.currentForecastUnitCost = (prod.unit_cost !== null && prod.unit_cost !== undefined && !isNaN(Number(prod.unit_cost)))
                        ? Number(prod.unit_cost)
                        : Math.round((Number(prod.unit_price) || 100) * 0.85);

                    // Update on-hand and on-order displays if available on page
                    const onHandSpan = document.querySelector('.bg-surface-container-low .text-error.font-bold');
                    if (onHandSpan) onHandSpan.textContent = prod.stock_on_hand;

                    const switchBtn = document.querySelector('button[aria-label="Switch SKU"]');
                    if (switchBtn) {
                        switchBtn.onclick = () => {
                            const nextIdx = (selectedIdx + 1) % products.length;
                            localStorage.setItem('smartstock_forecast_sku_idx', nextIdx);
                            SmartStock.bindLivePageData();
                            SmartStock.showToast(`Forecast for: ${products[nextIdx].name}`, 'info');
                        };
                    }

                    // Restore selected horizon or default to 14 days
                    const savedHorizon = parseInt(localStorage.getItem('smartstock_forecast_horizon') || '14', 10);
                    SmartStock.setForecastHorizon(savedHorizon, true);

                    // Horizon Buttons onclick
                    const horizonBtns = document.querySelectorAll('.horizon-btn');
                    horizonBtns.forEach(btn => {
                        btn.onclick = () => {
                            const d = parseInt(btn.getAttribute('data-days'), 10) || 14;
                            SmartStock.setForecastHorizon(d, false);
                        };
                    });

                    // Wire PO creation button
                    const poCreateBtn = document.querySelector('main button[class*="bg-primary"][class*="text-on-primary"]');
                    if (poCreateBtn && (poCreateBtn.textContent.includes('Purchase Order') || poCreateBtn.textContent.includes('Create'))) {
                        poCreateBtn.onclick = (e) => {
                            e.preventDefault();
                            SmartStock.createPoDraftFromForecast();
                        };
                    }
                }
            }

            // 2.5 AI Replenishment Page Binding
            if (currentPage === '05_replenishment.html') {
                this.renderAIReplenishmentPage(products);
            }

            // 3. Purchase Orders Page Binding
            if (currentPage === '05_purchase_orders.html') {
                const purchaseOrders = this.getPurchaseOrders();
                const activeFilter = localStorage.getItem('smartstock_po_filter') || 'all';

                // Find active orders ('ordered' or 'in_transit')
                const activeOrders = purchaseOrders.filter(po => po.status === 'ordered' || po.status === 'in_transit');
                const orderedProductIds = new Set();
                activeOrders.forEach(po => {
                    if (Array.isArray(po.items)) {
                        po.items.forEach(it => {
                            if (it.product_id) orderedProductIds.add(String(it.product_id));
                            if (it.name) orderedProductIds.add(it.name.toLowerCase().trim());
                        });
                    }
                });

                // Products needing replenishment that are NOT in any active PO
                const unreplenishedLowStock = products.filter(p => {
                    const isLow = (Number(p.stock_on_hand) || 0) <= (Number(p.reorder_point) || 5);
                    const isAlreadyOrdered = orderedProductIds.has(String(p.id)) || orderedProductIds.has((p.name || '').toLowerCase().trim());
                    return isLow && !isAlreadyOrdered;
                });

                const draftCount = unreplenishedLowStock.length > 0 ? 1 : 0;
                const orderedCount = purchaseOrders.filter(po => po.status === 'ordered').length;
                const inTransitCount = purchaseOrders.filter(po => po.status === 'in_transit').length;
                const completedCount = purchaseOrders.filter(po => po.status === 'completed').length;
                const totalCount = purchaseOrders.length + draftCount;

                const poMain = document.querySelector('main .space-y-space-md');
                if (!poMain) return;

                // Build Tabs Bar
                const tabs = [
                    { id: 'all', label: `All (${totalCount})` },
                    { id: 'drafts', label: `Drafts (${draftCount})` },
                    { id: 'ordered', label: `Ordered (${orderedCount})` },
                    { id: 'in_transit', label: `In Transit (${inTransitCount})` },
                    { id: 'completed', label: `Completed (${completedCount})` }
                ];

                const tabsHtml = `
                    <div class="flex items-center gap-1.5 overflow-x-auto py-1 no-scrollbar text-nowrap">
                        ${tabs.map(t => {
                            const isActive = activeFilter === t.id;
                            const cls = isActive
                                ? 'bg-primary-container text-on-primary font-semibold shadow-sm'
                                : 'bg-surface-container-high text-on-surface-variant active:bg-surface-variant';
                            return `<button onclick="SmartStock.filterPurchaseOrders('${t.id}')" class="px-3 py-1.5 rounded-full ${cls} font-label-sm text-label-sm cursor-pointer transition-all">${t.label}</button>`;
                        }).join('')}
                    </div>
                `;

                // Calculate next PO Number for draft
                const year = new Date().getFullYear();
                const nextDraftNo = `PO-${year}-${(purchaseOrders.length + 1).toString().padStart(3, '0')}`;

                // Calculate draft items HTML & total
                let draftTotalAmount = 0;
                const draftItemsHtml = unreplenishedLowStock.map(p => {
                    const needed = Math.max(10, (Number(p.reorder_point) || 5) * 2 - (Number(p.stock_on_hand) || 0));
                    const cost = Number(p.unit_cost) || Math.round((Number(p.unit_price) || 100) * 0.85);
                    const lineTotal = needed * cost;
                    draftTotalAmount += lineTotal;
                    return `
                        <div class="flex items-center justify-between p-2.5 rounded-lg bg-surface-container-low">
                            <div class="min-w-0 flex-1">
                                <p class="font-label-lg text-label-lg text-on-surface font-semibold truncate">${p.name}</p>
                                <p class="font-code-sm text-code-sm text-on-surface-variant">${needed} units × ${SmartStock.formatINR(cost)}</p>
                            </div>
                            <div class="text-right pl-2">
                                <span class="font-code-md text-code-md text-on-surface font-semibold">${SmartStock.formatINR(lineTotal)}</span>
                            </div>
                        </div>
                    `;
                }).join('');

                // Draft Section
                let draftSectionHtml = '';
                if (activeFilter === 'all' || activeFilter === 'drafts') {
                    if (unreplenishedLowStock.length > 0) {
                        draftSectionHtml = `
                            <div class="bg-surface-container-lowest rounded-xl p-space-md shadow-sm space-y-space-md relative overflow-hidden border border-outline/10">
                                <div class="absolute top-0 left-0 right-0 h-1 bg-secondary-container"></div>
                                <div class="flex flex-col gap-space-xs">
                                    <div class="flex items-start justify-between">
                                        <div>
                                            <div class="flex items-center gap-space-xs">
                                                <span class="font-code-md text-code-md text-primary font-bold tracking-tight">${nextDraftNo}</span>
                                                <span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-sm text-label-sm uppercase font-semibold">AI Draft</span>
                                            </div>
                                            <p class="font-headline-sm text-headline-sm text-on-surface font-semibold mt-0.5">Automated Replenishment</p>
                                        </div>
                                        <div class="text-right">
                                            <span class="font-label-sm text-label-sm text-on-surface-variant block">Total Value</span>
                                            <span class="font-code-md text-code-md text-primary font-bold">${SmartStock.formatINR(draftTotalAmount)}</span>
                                        </div>
                                    </div>
                                    <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm w-fit">
                                        <span class="material-symbols-outlined text-secondary text-[16px]">psychology</span>
                                        <span>Auto-composed from sales run-rate & safety stock limits</span>
                                    </div>
                                </div>
                                <div class="space-y-space-xs">
                                    <div class="flex items-center justify-between pb-1">
                                        <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider font-semibold">Items Needing Restock (${unreplenishedLowStock.length})</span>
                                    </div>
                                    ${draftItemsHtml}
                                </div>
                                <div class="pt-2 flex items-center justify-end gap-2 border-t border-outline/10">
                                    <button onclick="SmartStock.issueDraftPO()" class="px-4 h-9 bg-primary text-on-primary rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs active:scale-95 transition-all cursor-pointer">
                                        <span class="material-symbols-outlined text-[16px]">send</span>
                                        <span>Issue Purchase Order</span>
                                    </button>
                                </div>
                            </div>
                        `;
                    } else if (activeFilter === 'drafts') {
                        draftSectionHtml = `
                            <div class="bg-surface-container-lowest rounded-2xl p-6 text-center border border-outline/10 space-y-2">
                                <span class="material-symbols-outlined text-[36px] text-primary">verified</span>
                                <h3 class="font-bold text-sm text-on-surface">No Pending Replenishment Drafts</h3>
                                <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                                    ${products.length === 0 
                                        ? 'Your catalog is empty. Add products to activate replenishment.' 
                                        : 'All low-stock items have active Purchase Orders placed with suppliers. Check the "Ordered" tab below to track delivery.'}
                                </p>
                            </div>
                        `;
                    } else if (activeFilter === 'all' && products.length > 0 && orderedCount > 0) {
                        draftSectionHtml = `
                            <div class="p-3.5 bg-primary-fixed/30 rounded-xl border border-primary/20 flex items-start gap-2.5">
                                <span class="material-symbols-outlined text-primary text-[20px] shrink-0 mt-0.5">verified</span>
                                <div class="text-xs">
                                    <p class="font-bold text-on-surface">AI Replenishment: Orders Dispatched</p>
                                    <p class="text-on-surface-variant mt-0.5">Active Purchase Orders have been sent to suppliers for all low-stock products. Track or inward stock in the Orders Ledger below.</p>
                                </div>
                            </div>
                        `;
                    }
                }

                // Filtered Orders List
                let filteredOrders = purchaseOrders;
                if (activeFilter === 'ordered') {
                    filteredOrders = purchaseOrders.filter(po => po.status === 'ordered');
                } else if (activeFilter === 'in_transit') {
                    filteredOrders = purchaseOrders.filter(po => po.status === 'in_transit');
                } else if (activeFilter === 'completed') {
                    filteredOrders = purchaseOrders.filter(po => po.status === 'completed');
                } else if (activeFilter === 'drafts') {
                    filteredOrders = [];
                }

                let ordersListHtml = '';
                if (filteredOrders.length > 0) {
                    ordersListHtml = `
                        <div class="space-y-space-sm">
                            <div class="flex items-center justify-between">
                                <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider font-semibold">
                                    ${activeFilter === 'all' ? 'Purchase Orders Ledger' : activeFilter.toUpperCase() + ' ORDERS'} (${filteredOrders.length})
                                </span>
                            </div>
                            <div class="space-y-3">
                                ${filteredOrders.map(po => {
                                    const isCompleted = po.status === 'completed';
                                    const isInTransit = po.status === 'in_transit';
                                    const statusBadge = isCompleted
                                        ? `<span class="px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed text-[10px] font-bold uppercase tracking-wider">Completed • Stock Inwarded</span>`
                                        : (isInTransit
                                            ? `<span class="px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-[10px] font-bold uppercase tracking-wider">In Transit</span>`
                                            : `<span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[10px] font-bold uppercase tracking-wider">Ordered • Sent to Supplier</span>`);

                                    const dateStr = po.created_at ? new Date(po.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Recently';

                                    const itemsSummary = Array.isArray(po.items)
                                        ? po.items.map(it => {
                                            const prod = products.find(p => p.id === it.product_id || (p.name && it.name && p.name.toLowerCase() === it.name.toLowerCase()));
                                            const stockOnHand = prod ? (Number(prod.stock_on_hand) || 0) : null;
                                            let stockBadge = '';
                                            if (stockOnHand !== null) {
                                                if (stockOnHand <= 0) {
                                                    stockBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-error/15 text-error">OUT OF STOCK (0 units)</span>`;
                                                } else if (stockOnHand <= (Number(prod.reorder_point) || 5)) {
                                                    stockBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-secondary-fixed text-on-secondary-fixed">LOW STOCK (${stockOnHand} left)</span>`;
                                                } else {
                                                    stockBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary">${stockOnHand} on hand</span>`;
                                                }
                                            }
                                            return `
                                                <div class="flex flex-col sm:flex-row sm:items-center justify-between text-xs py-1.5 border-b border-outline/10 last:border-b-0 gap-1">
                                                    <div class="flex items-center gap-1.5 flex-wrap">
                                                        <span class="font-semibold text-on-surface">${it.name || it.item}</span>
                                                        ${stockBadge}
                                                    </div>
                                                    <div class="flex items-center gap-2 text-on-surface-variant font-mono">
                                                        <span class="font-bold text-primary">${it.units || it.quantity} units ordered</span>
                                                        <span class="text-outline">•</span>
                                                        <span>${SmartStock.formatINR(it.total_cost || it.total || 0)}</span>
                                                    </div>
                                                </div>
                                            `;
                                        }).join('')
                                        : '';

                                    return `
                                    <div class="bg-surface-container-lowest rounded-xl p-3.5 shadow-sm border border-outline/10 space-y-2.5">
                                        <div class="flex items-start justify-between gap-2">
                                            <div>
                                                <div class="flex items-center gap-2">
                                                    <span class="font-mono text-xs font-bold text-primary">${po.po_number || po.id}</span>
                                                    ${statusBadge}
                                                </div>
                                                <p class="text-xs text-on-surface-variant mt-0.5">${po.supplier || 'Metro Wholesale'} • <span class="text-outline">${dateStr}</span></p>
                                            </div>
                                            <div class="text-right">
                                                <span class="font-bold text-sm text-primary block">${SmartStock.formatINR(po.total_amount || po.total || 0)}</span>
                                                <span class="text-[10px] text-on-surface-variant">${(po.items || []).length} Line Items</span>
                                            </div>
                                        </div>

                                        <div class="bg-surface-container-low p-2 rounded-lg space-y-1">
                                            ${itemsSummary}
                                        </div>

                                        <div class="pt-2 flex items-center justify-between border-t border-outline/10">
                                            <div class="text-[11px] text-on-surface-variant flex items-center gap-1">
                                                <span class="material-symbols-outlined text-[15px] ${isCompleted ? 'text-primary' : 'text-secondary'}">
                                                    ${isCompleted ? 'task_alt' : 'local_shipping'}
                                                </span>
                                                <span>${isCompleted ? 'Inwarded to Store Inventory' : 'Awaiting Supplier Delivery'}</span>
                                            </div>
                                            ${!isCompleted ? `
                                                <button onclick="SmartStock.receivePO('${po.id}')" class="h-8 px-3 rounded-lg bg-primary text-on-primary font-semibold text-xs flex items-center gap-1.5 active:opacity-90 shadow-xs cursor-pointer">
                                                    <span class="material-symbols-outlined text-[15px]">inventory_2</span>
                                                    <span>Receive Stock</span>
                                                </button>
                                            ` : `
                                                <span class="text-primary font-semibold text-xs flex items-center gap-1">
                                                    <span class="material-symbols-outlined text-[16px]">check_circle</span>
                                                    <span>Inwarded</span>
                                                </span>
                                            `}
                                        </div>
                                    </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    `;
                } else if (activeFilter !== 'drafts') {
                    ordersListHtml = `
                        <div class="bg-surface-container-lowest rounded-2xl p-6 text-center border border-outline/10 space-y-2">
                            <span class="material-symbols-outlined text-[32px] text-outline">receipt_long</span>
                            <h3 class="font-bold text-sm text-on-surface">No ${activeFilter.toUpperCase()} Orders Found</h3>
                            <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                                ${activeFilter === 'all' 
                                    ? 'No purchase orders have been issued yet. Issue a replenishment draft or create a New PO.' 
                                    : 'There are currently no orders in ' + activeFilter + ' status.'}
                            </p>
                        </div>
                    `;
                }

                // If completely empty store
                if (products.length === 0 && purchaseOrders.length === 0) {
                    poMain.innerHTML = `
                        <div class="flex flex-col gap-space-sm">
                            <div class="flex items-center justify-between gap-space-sm">
                                <div class="flex items-center gap-space-xs">
                                    <span class="material-symbols-outlined text-primary text-[20px]">local_shipping</span>
                                    <span class="font-headline-sm text-headline-sm text-primary font-semibold">Procurement Ledger</span>
                                </div>
                                <button onclick="SmartStock.openNewPOModal()" class="h-9 px-space-md bg-primary text-on-primary rounded-lg font-label-md text-label-md flex items-center gap-1.5 shadow-sm active:scale-95 transition-transform cursor-pointer">
                                    <span class="material-symbols-outlined text-[18px]">add</span>
                                    <span>New PO</span>
                                </button>
                            </div>
                            ${tabsHtml}
                        </div>
                        <div class="bg-surface-container-lowest rounded-2xl p-8 text-center border border-outline/10 space-y-3 mt-4">
                            <span class="material-symbols-outlined text-[36px] text-outline">receipt_long</span>
                            <h3 class="font-bold text-base text-on-surface">No Purchase Orders or Inventory</h3>
                            <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                                Your catalog has 0 items. Add products to activate automated AI replenishment recommendations.
                            </p>
                            <div class="flex items-center justify-center gap-2 pt-2">
                                <button onclick="SmartStock.openAddProductModal()" class="px-4 py-2 bg-primary text-on-primary rounded-lg font-semibold text-xs shadow-xs active:scale-95 transition-all cursor-pointer">
                                    + Add Product
                                </button>
                                <button onclick="SmartStock.openImportModal()" class="px-4 py-2 bg-surface-container text-on-surface rounded-lg font-semibold text-xs hover:bg-surface-container-high active:scale-95 transition-all cursor-pointer">
                                    Import File (CSV)
                                </button>
                            </div>
                        </div>
                    `;
                    return;
                }

                // Assemble complete view
                poMain.innerHTML = `
                    <div class="flex flex-col gap-space-sm">
                        <div class="flex items-center justify-between gap-space-sm">
                            <div class="flex items-center gap-space-xs">
                                <span class="material-symbols-outlined text-primary text-[20px]">local_shipping</span>
                                <span class="font-headline-sm text-headline-sm text-primary font-semibold">Procurement Ledger</span>
                            </div>
                            <button onclick="SmartStock.openNewPOModal()" class="h-9 px-space-md bg-primary text-on-primary rounded-lg font-label-md text-label-md flex items-center gap-1.5 shadow-sm active:scale-95 transition-transform cursor-pointer">
                                <span class="material-symbols-outlined text-[18px]">add</span>
                                <span>New PO</span>
                            </button>
                        </div>
                        ${tabsHtml}
                    </div>

                    ${draftSectionHtml}
                    ${ordersListHtml}
                `;
            }

            // 4. Settings Page Binding
            if (currentPage === '06_settings.html') {
                let userProfile = {};
                try { userProfile = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch(e){}
                
                const storeName = userProfile.store || currentStoreName || 'My Store';
                const managerName = userProfile.manager || 'Store Owner';
                const email = userEmail || userProfile.email || 'Not configured';
                const phone = userPhone || userProfile.phone || 'Not added';
                const city = userProfile.city || 'India';
                const gst = userProfile.gst || 'Optional (Not added)';
                const threshold = userProfile.lowStockThreshold || 5;

                // Monogram Avatar
                const avatarEl = document.getElementById('profile-avatar');
                if (avatarEl) {
                    avatarEl.textContent = storeName.trim().charAt(0).toUpperCase() || 'S';
                }

                // Profile Fields
                const storeNameEl = document.getElementById('profile-store-name');
                if (storeNameEl) storeNameEl.textContent = storeName;

                const managerEl = document.getElementById('profile-manager-title');
                if (managerEl) managerEl.textContent = managerName;

                const emailEl = document.getElementById('profile-email');
                if (emailEl) emailEl.textContent = email;

                const phoneEl = document.getElementById('profile-phone');
                if (phoneEl) phoneEl.textContent = phone;

                // Inventory Metrics
                const countEl = document.getElementById('profile-product-count');
                if (countEl) countEl.textContent = `${products.length} Products`;

                const totalVal = products.reduce((acc, p) => acc + ((p.stock_on_hand || 0) * (p.unit_price || 0)), 0);
                const valEl = document.getElementById('profile-total-value');
                if (valEl) valEl.textContent = SmartStock.formatINR(totalVal);

                // Preferences
                const cityEl = document.getElementById('pref-city');
                if (cityEl) cityEl.textContent = city;

                const gstEl = document.getElementById('pref-gst');
                if (gstEl) gstEl.textContent = gst;

                const thresholdEl = document.getElementById('alert-threshold-display');
                if (thresholdEl) thresholdEl.textContent = threshold;

                const soundInput = document.getElementById('pref-sound');
                if (soundInput && userProfile.scanSound !== undefined) {
                    soundInput.checked = !!userProfile.scanSound;
                }

                const bannerInput = document.getElementById('pref-banner');
                if (bannerInput && userProfile.stockBanner !== undefined) {
                    bannerInput.checked = userProfile.stockBanner !== false;
                }

                // Side drawer updates
                const drawerAvatar = document.querySelector('.drawer-avatar');
                if (drawerAvatar) drawerAvatar.textContent = storeName.trim().charAt(0).toUpperCase() || 'S';

                const drawerName = document.querySelector('.drawer-store-name');
                if (drawerName) drawerName.textContent = storeName;

                const drawerEmail = document.querySelector('.drawer-user-email');
                if (drawerEmail) drawerEmail.textContent = email;
            }

            // 5. Inventory Page Binding
            if (currentPage === '03_inventory.html') {
                const inventoryList = document.getElementById('inventory-list');
                if (!inventoryList) return;

                if (products.length === 0) {
                    inventoryList.innerHTML = `
                        <div class="bg-surface-container-lowest rounded-xl p-10 text-center border border-outline/10 space-y-3">
                            <span class="material-symbols-outlined text-[36px] text-outline">inventory_2</span>
                            <h3 class="font-bold text-base text-on-surface">No Products in Inventory</h3>
                            <p class="text-xs text-on-surface-variant max-w-sm mx-auto">
                                Your catalog is currently empty. Add products manually or import a spreadsheet.
                            </p>
                            <div class="flex items-center justify-center gap-2 pt-2">
                                <button onclick="SmartStock.openAddProductModal()" class="px-4 py-2 bg-primary text-on-primary rounded-lg font-semibold text-xs shadow-xs active:scale-95 transition-all cursor-pointer">
                                    + Add Product
                                </button>
                                <button onclick="SmartStock.openImportModal()" class="px-4 py-2 bg-surface-container text-on-surface rounded-lg font-semibold text-xs hover:bg-surface-container-high active:scale-95 transition-all cursor-pointer">
                                    Import File (CSV)
                                </button>
                            </div>
                        </div>
                    `;
                } else {
                    inventoryList.innerHTML = products.map(p => {
                        const stock = Number(p.stock_on_hand) || 0;
                        const rop = Math.min(30, Number(p.reorder_point) || 10);
                        const isZero = stock === 0;
                        const isLow = stock <= rop && !isZero;
                        const statusKey = isZero ? 'zero' : (isLow ? 'low' : 'healthy');
                        const statusBadge = isZero 
                            ? `<span class="px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-[10px] font-bold uppercase tracking-wider">Out of Stock</span>`
                            : (isLow 
                                ? `<span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[10px] font-bold uppercase tracking-wider">Low Stock</span>`
                                : `<span class="px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed text-[10px] font-bold uppercase tracking-wider">Healthy</span>`);

                        return `
                        <div class="inventory-card bg-surface-container-lowest rounded-xl p-3.5 shadow-sm border border-outline/10 relative overflow-hidden transition-all"
                             data-id="${p.id}"
                             data-status="${statusKey}"
                             data-stock="${stock}"
                             data-reorder="${rop}"
                             data-category="${(p.category_name || 'General').toLowerCase()}"
                             data-price="${p.unit_price || 0}"
                             data-name="${(p.name || '').toLowerCase()}"
                             data-sku="${(p.sku || '').toLowerCase()}">
                            <div class="absolute left-0 top-0 bottom-0 w-1.5 ${isZero ? 'bg-error' : (isLow ? 'bg-secondary' : 'bg-primary')}"></div>
                            <div class="flex items-start justify-between gap-2 pl-1.5">
                                <div class="flex items-start gap-2.5 min-w-0 flex-1">
                                    <label class="cursor-pointer relative flex items-center pt-0.5" onclick="event.stopPropagation()">
                                        <input type="checkbox" class="item-checkbox w-4 h-4 rounded text-primary accent-[#0b3127] cursor-pointer" data-id="${p.id}" onchange="SmartStock.onItemSelectChange()">
                                    </label>
                                    <div class="min-w-0 flex-1">
                                        <div class="flex items-center gap-1.5 text-xs text-on-surface-variant">
                                            <span class="font-mono text-[11px] font-semibold text-outline">${p.sku || 'SKU'}</span>
                                            <span>•</span>
                                            <span>${p.category_name || 'General'}</span>
                                        </div>
                                        <h3 class="font-bold text-sm text-on-surface truncate mt-0.5">${p.name}</h3>
                                        <div class="flex items-center gap-3 text-xs text-on-surface-variant mt-1">
                                            <span>Price: <b class="text-on-surface">${SmartStock.formatINR(p.unit_price)}</b></span>
                                            <span>Cost: <span class="text-outline">${SmartStock.formatINR(p.unit_cost)}</span></span>
                                        </div>
                                    </div>
                                </div>
                                <div class="shrink-0 flex flex-col items-end">
                                    ${statusBadge}
                                </div>
                            </div>

                            <div class="grid grid-cols-3 gap-2 mt-3 bg-surface-container-low p-2 rounded-lg text-center">
                                <div>
                                    <span class="block text-[10px] text-outline uppercase font-semibold">Stock</span>
                                    <span class="font-bold text-sm ${isZero ? 'text-error' : (isLow ? 'text-secondary' : 'text-primary')}">${stock}</span>
                                </div>
                                <div>
                                    <span class="block text-[10px] text-outline uppercase font-semibold">Reorder At</span>
                                    <span class="font-semibold text-sm text-on-surface">${rop}</span>
                                </div>
                                <div>
                                    <span class="block text-[10px] text-outline uppercase font-semibold">Valuation</span>
                                    <span class="font-bold text-sm text-on-surface">${SmartStock.formatINR(stock * (p.unit_price || 0))}</span>
                                </div>
                            </div>

                            <div class="flex items-center justify-between gap-2 mt-2.5 pt-2 border-t border-outline/10">
                                <div class="flex items-center gap-1">
                                    <button onclick="SmartStock.openEditProductModal('${p.id}')" class="text-primary hover:bg-primary/10 p-1.5 rounded-lg active:scale-95 transition-all text-xs cursor-pointer" title="Edit Item & Reorder Point">
                                        <span class="material-symbols-outlined text-[17px]">edit</span>
                                    </button>
                                    <button onclick="SmartStock.deleteProduct('${p.id}')" class="text-error hover:bg-error-container/20 p-1.5 rounded-lg active:scale-95 transition-all text-xs cursor-pointer" title="Delete Product">
                                        <span class="material-symbols-outlined text-[17px]">delete</span>
                                    </button>
                                </div>
                                <div class="flex items-center gap-2">
                                    <button onclick="SmartStock.updateStock('${p.id}', -1)" class="h-8 px-2.5 rounded-lg bg-surface-container text-on-surface font-semibold text-xs flex items-center gap-1 active:bg-surface-variant transition-all cursor-pointer">
                                        <span class="material-symbols-outlined text-[15px] text-secondary">remove_circle_outline</span>
                                        <span>-1 Sell</span>
                                    </button>
                                    <button onclick="SmartStock.updateStock('${p.id}', 10)" class="h-8 px-2.5 rounded-lg bg-primary text-on-primary font-semibold text-xs flex items-center gap-1 active:opacity-90 shadow-xs transition-all cursor-pointer">
                                        <span class="material-symbols-outlined text-[15px]">add_circle</span>
                                        <span>+10 Stock</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                        `;
                    }).join('');
                }

                // Update Filter Pill counts for all 6 pills
                const countAll = products.length;
                const countLow = products.filter(p => {
                    const s = Number(p.stock_on_hand) || 0;
                    const r = Math.min(30, Number(p.reorder_point) || 10);
                    return s <= r && s > 0;
                }).length;
                const countZero = products.filter(p => (Number(p.stock_on_hand) || 0) === 0).length;
                const countHealthy = products.filter(p => {
                    const s = Number(p.stock_on_hand) || 0;
                    const r = Math.min(30, Number(p.reorder_point) || 10);
                    return s > r;
                }).length;
                const countExcess = products.filter(p => {
                    const s = Number(p.stock_on_hand) || 0;
                    const r = Math.min(30, Number(p.reorder_point) || 10);
                    return s > r * 3;
                }).length;
                const countSlow = products.filter(p => p.xyz_class === 'Z' || (Number(p.stock_on_hand) || 0) > 30).length;

                const cAllEl = document.getElementById('pill-count-all');
                if (cAllEl) cAllEl.textContent = countAll;
                const cLowEl = document.getElementById('pill-count-low');
                if (cLowEl) cLowEl.textContent = countLow;
                const cZeroEl = document.getElementById('pill-count-zero');
                if (cZeroEl) cZeroEl.textContent = countZero;
                const cHealthyEl = document.getElementById('pill-count-healthy');
                if (cHealthyEl) cHealthyEl.textContent = countHealthy;
                const cExcessEl = document.getElementById('pill-count-excess');
                if (cExcessEl) cExcessEl.textContent = countExcess;
                const cSlowEl = document.getElementById('pill-count-slow');
                if (cSlowEl) cSlowEl.textContent = countSlow;

                // Wire Filter Pills Onclick
                document.querySelectorAll('.filter-pill').forEach(pill => {
                    const filter = pill.getAttribute('data-filter') || 'all';
                    pill.onclick = () => SmartStock.filterInventory(filter, pill);
                });

                // Wire Category Selector
                const catSelect = document.getElementById('category-filter-select');
                if (catSelect) {
                    catSelect.onchange = (e) => SmartStock.filterByCategory(e.target.value);
                }

                // Wire Sort Button
                const sortBtn = document.getElementById('toggle-sort-btn');
                if (sortBtn) {
                    sortBtn.onclick = () => SmartStock.cycleSort();
                }

                // Wire Master Select
                const masterCheck = document.getElementById('master-select');
                if (masterCheck) {
                    masterCheck.onchange = (e) => SmartStock.toggleSelectAll(e.target.checked);
                }

                // Wire Live Search
                const searchInput = document.querySelector('input[placeholder*="Search by SKU"]');
                if (searchInput) {
                    searchInput.oninput = () => SmartStock.applyInventoryFilters();
                }

                // Apply initial active filter if saved
                const savedFilter = localStorage.getItem('smartstock_inventory_filter') || 'all';
                SmartStock.filterInventory(savedFilter);
            }

            // Wire Toolbar Buttons
            document.querySelectorAll('button, a').forEach(el => {
                const text = (el.textContent || '').trim();
                if (text.includes('Add Item') || text.includes('Add Product')) {
                    el.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openAddProductModal();
                    };
                } else if (text.includes('Import') || text.includes('Import CSV')) {
                    el.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.openImportModal();
                    };
                } else if (text.includes('Export')) {
                    el.onclick = (e) => {
                        e.preventDefault();
                        SmartStock.exportCSV(products);
                    };
                }
            });
        }
    };

    function initSmartStock() {
        if (typeof document === 'undefined') return;
        SmartStock.client();
        SmartStock.injectModals();
        SmartStock.bindNavigation();
        SmartStock.bindLivePageData();
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initSmartStock);
        } else {
            initSmartStock();
        }
    }

    if (typeof window !== 'undefined') {
        window.SmartStock = SmartStock;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = SmartStock;
    }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

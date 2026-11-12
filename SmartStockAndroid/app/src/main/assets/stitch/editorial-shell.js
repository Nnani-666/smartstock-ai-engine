/**
 * SmartStock — Premium Editorial Shell & Navigation Infrastructure
 * Renders unified Sidebar, Masthead, Light/Dark Theme Switcher,
 * and Two-Level Intelligence Switcher (Business vs Technical/Academic).
 */
(function (window) {
    const NAV_ITEMS = [
        { id: 'overview', label: 'Dashboard', icon: 'dashboard', href: '02_overview.html', path: 'overview' },
        { id: 'inventory', label: 'Inventory', icon: 'inventory_2', href: '03_inventory.html', path: 'inventory' },
        { id: 'sales', label: 'Sales & POS', icon: 'point_of_sale', href: '07_sales.html', path: 'sales' },
        { id: 'orders', label: 'Purchase Orders', icon: 'receipt_long', href: '05_purchase_orders.html', path: 'orders' },
        {
            id: 'ai-group',
            label: 'AI Intelligence',
            icon: 'neurology',
            isGroup: true,
            children: [
                { id: 'replenishment', label: 'Replenishment Engine', icon: 'auto_awesome', href: '05_replenishment.html', path: 'ai-insights-&-replenishment' },
                { id: 'forecasts', label: 'Demand Forecasting', icon: 'query_stats', href: '04_forecasts.html', path: 'forecasts' },
                { id: 'anomalies', label: 'Anomaly Detection', icon: 'crisis_alert', href: '08_anomalies.html', path: 'anomalies' },
                { id: 'segmentation', label: 'SKU Segmentation', icon: 'grid_view', href: '09_segmentation.html', path: 'segmentation' }
            ]
        },
        { id: 'analytics', label: 'Analytics & Reports', icon: 'analytics', href: '11_analytics.html', path: 'analytics' },
        { id: 'suppliers', label: 'Suppliers', icon: 'local_shipping', href: '12_suppliers.html', path: 'suppliers' },
        { id: 'assistant', label: 'Smart Assistant', icon: 'smart_toy', href: '10_assistant.html', path: 'assistant' }
    ];

    const BOTTOM_ITEMS = [
        { id: 'settings', label: 'Settings & Profile', icon: 'settings', href: '06_settings.html', path: 'settings' }
    ];

    function getTheme() {
        return localStorage.getItem('smartstock_theme') || 'light';
    }

    function applyTheme(theme) {
        const clean = theme === 'dark' ? 'dark' : 'light';
        localStorage.setItem('smartstock_theme', clean);
        document.documentElement.setAttribute('data-theme', clean);
        if (clean === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        document.querySelectorAll('.ed-theme-icon').forEach(el => {
            el.textContent = clean === 'dark' ? 'light_mode' : 'dark_mode';
        });
        document.querySelectorAll('.ed-theme-label').forEach(el => {
            el.textContent = clean === 'dark' ? 'Dark' : 'Light';
        });
        window.dispatchEvent(new CustomEvent('smartstock:themechange', { detail: { theme: clean } }));
    }

    function toggleTheme() {
        applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
    }

    function getIntelligenceMode() {
        return localStorage.getItem('smartstock_intelligence_mode') || 'business';
    }

    function applyIntelligenceMode(mode) {
        const clean = mode === 'technical' ? 'technical' : 'business';
        localStorage.setItem('smartstock_intelligence_mode', clean);
        if (document.body) {
            document.body.setAttribute('data-intel', clean);
        }
        document.querySelectorAll('.ed-intel-btn').forEach(btn => {
            const btnMode = btn.getAttribute('data-intel-choice');
            if (btnMode === clean) {
                btn.style.backgroundColor = 'var(--bg-surface)';
                btn.style.color = 'var(--accent-primary)';
                btn.style.fontWeight = '700';
                btn.style.boxShadow = '0 1px 2px rgba(0,0,0,0.08)';
            } else {
                btn.style.backgroundColor = 'transparent';
                btn.style.color = 'var(--text-secondary)';
                btn.style.fontWeight = '500';
                btn.style.boxShadow = 'none';
            }
        });
        const badge = document.getElementById('ed-mode-kicker');
        if (badge) {
            badge.textContent = clean === 'technical' ? 'Academic / Technical Mode' : 'Shopkeeper Business Mode';
        }
        window.dispatchEvent(new CustomEvent('smartstock:intelchange', { detail: { mode: clean } }));
    }

    function toggleDrawer(open) {
        const drawer = document.getElementById('side-drawer');
        const backdrop = document.getElementById('drawer-backdrop');
        if (!drawer || !backdrop) return;
        if (open) {
            drawer.classList.add('open');
            backdrop.classList.add('open');
        } else {
            drawer.classList.remove('open');
            backdrop.classList.remove('open');
        }
    }

    function renderShell(options = {}) {
        const pageId = options.pageId || 'overview';
        const title = options.title || 'Overview';
        const subtitle = options.subtitle || '';

        applyTheme(getTheme());
        if (document.body) {
            document.body.setAttribute('data-intel', getIntelligenceMode());
        }

        // Remove existing shell chrome if re-mounting
        const oldBackdrop = document.getElementById('drawer-backdrop');
        const oldDrawer = document.getElementById('side-drawer');
        const oldHeader = document.getElementById('ed-masthead');
        const oldBottomNav = document.getElementById('ed-mobile-bottom-nav');
        if (oldBackdrop) oldBackdrop.remove();
        if (oldDrawer) oldDrawer.remove();
        if (oldHeader) oldHeader.remove();
        if (oldBottomNav) oldBottomNav.remove();

        let user = {};
        try { user = JSON.parse(localStorage.getItem('smartstock_user') || '{}'); } catch (e) {}
        const storeName = user.store || localStorage.getItem('smartstock_last_active_store') || 'My Store';
        const initial = (storeName.trim().charAt(0) || 'S').toUpperCase();

        // Backdrop
        const backdrop = document.createElement('div');
        backdrop.id = 'drawer-backdrop';
        backdrop.className = 'fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40 opacity-0 pointer-events-none transition-opacity duration-200 lg:hidden';
        backdrop.onclick = () => toggleDrawer(false);

        // Build Navigation Links HTML
        const isActive = (item) => item.id === pageId;
        const navHtml = NAV_ITEMS.map(item => {
            if (item.isGroup) {
                const groupActive = item.children.some(c => c.id === pageId);
                return `
                    <div class="pt-2 pb-1">
                        <div class="px-3 pb-1.5 flex items-center justify-between">
                            <span class="ed-kicker text-[10px]">${item.label}</span>
                            <span class="text-[9px] font-tabular px-1.5 py-0.5 rounded-full" style="background:var(--accent-secondary-soft); color:var(--accent-secondary); font-weight:700;">4 MODULES</span>
                        </div>
                        <div class="space-y-0.5">
                            ${item.children.map(child => {
                                const active = isActive(child);
                                return `
                                    <a href="${child.href}" data-path="${child.path}"
                                       class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors ${active ? 'font-semibold' : 'font-medium'}"
                                       style="${active
                                           ? 'background:var(--accent-primary-soft); color:var(--accent-primary); border-left:2.5px solid var(--accent-primary);'
                                           : 'color:var(--text-secondary);'}">
                                        <span class="material-symbols-outlined text-[18px]">${child.icon}</span>
                                        <span class="truncate">${child.label}</span>
                                    </a>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
            const active = isActive(item);
            return `
                <a href="${item.href}" data-path="${item.path}"
                   class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13.5px] transition-colors ${active ? 'font-semibold' : 'font-medium'}"
                   style="${active
                       ? 'background:var(--accent-primary-soft); color:var(--accent-primary); border-left:2.5px solid var(--accent-primary);'
                       : 'color:var(--text-secondary);'}">
                    <span class="material-symbols-outlined text-[19px]">${item.icon}</span>
                    <span class="truncate">${item.label}</span>
                </a>
            `;
        }).join('');

        // Left Sidebar / Mobile Drawer
        const drawer = document.createElement('aside');
        drawer.id = 'side-drawer';
        drawer.className = 'ed-sidebar';
        drawer.innerHTML = `
            <div class="h-16 px-4 flex items-center justify-between border-b ed-rule shrink-0">
                <a href="02_overview.html" class="flex items-center gap-2.5 min-w-0">
                    <img src="../assets/smartstock-logo.svg" alt="SmartStock" class="w-8 h-8 rounded-lg object-cover border ed-rule" />
                    <div class="min-w-0">
                        <span class="font-editorial text-[19px] font-semibold tracking-tight block leading-none" style="color:var(--text-primary);">SmartStock</span>
                        <span class="ed-kicker text-[9px] block mt-0.5">Retail Intelligence</span>
                    </div>
                </a>
                <button type="button" aria-label="Close navigation" onclick="SmartStockEditorial.toggleDrawer(false)" class="lg:hidden w-9 h-9 rounded-lg flex items-center justify-center" style="color:var(--text-secondary);">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <div class="px-3 py-3 border-b ed-rule shrink-0">
                <button type="button" onclick="if(window.SmartStock) SmartStock.openStoreSwitcherModal()" class="w-full p-2.5 rounded-lg flex items-center justify-between gap-2 text-left transition-colors ed-well cursor-pointer">
                    <div class="flex items-center gap-2.5 min-w-0">
                        <span class="material-symbols-outlined text-[19px]" style="color:var(--accent-secondary);">storefront</span>
                        <div class="min-w-0">
                            <p class="drawer-store-name text-[12.5px] font-semibold truncate" style="color:var(--text-primary);"></p>
                            <p class="font-tabular text-[10px]" style="color:var(--text-secondary);">INR Register • Active</p>
                        </div>
                    </div>
                    <span class="material-symbols-outlined text-[16px]" style="color:var(--text-muted);">unfold_more</span>
                </button>
            </div>

            <nav class="flex-1 overflow-y-auto px-3 py-3 space-y-0.5" aria-label="Primary Navigation">
                ${navHtml}
            </nav>

            <div class="p-3 border-t ed-rule space-y-1 shrink-0" style="background:var(--bg-subtle);">
                ${BOTTOM_ITEMS.map(item => `
                    <a href="${item.href}" data-path="${item.path}"
                       class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] ${pageId === item.id ? 'font-semibold' : 'font-medium'}"
                       style="${pageId === item.id ? 'color:var(--accent-primary);' : 'color:var(--text-secondary);'}">
                        <span class="material-symbols-outlined text-[18px]">${item.icon}</span>
                        <span>${item.label}</span>
                    </a>
                `).join('')}
                <a href="01_signin.html" data-path="login" onclick="if(window.SmartStock) SmartStock.signOut(); return false;"
                   class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-semibold cursor-pointer" style="color:var(--status-danger);">
                    <span class="material-symbols-outlined text-[18px]">logout</span>
                    <span>Sign Out</span>
                </a>
            </div>
        `;

        // Set textContent safely for store name
        const storeNameEl = drawer.querySelector('.drawer-store-name');
        if (storeNameEl) storeNameEl.textContent = storeName;

        // Top Editorial Masthead
        const header = document.createElement('header');
        header.id = 'ed-masthead';
        header.className = 'fixed top-0 right-0 left-0 lg:left-[256px] z-30 h-16 px-4 md:px-6 flex items-center justify-between border-b ed-rule transition-colors';
        header.style.backgroundColor = 'var(--bg-surface)';

        header.innerHTML = `
            <div class="flex items-center gap-3 min-w-0">
                <button type="button" aria-label="Open navigation menu" onclick="SmartStockEditorial.toggleDrawer(true)" class="lg:hidden w-10 h-10 -ml-1 rounded-lg flex items-center justify-center" style="color:var(--text-primary);">
                    <span class="material-symbols-outlined text-[22px]">menu</span>
                </button>
                <div class="min-w-0">
                    <div class="flex items-center gap-2">
                        <h1 class="font-editorial text-[20px] md:text-[22px] font-semibold truncate" style="color:var(--text-primary);" id="ed-page-title"></h1>
                        <span id="ed-mode-kicker" class="hidden xl:inline-block ed-kicker px-2 py-0.5 rounded-full" style="background:var(--bg-subtle);">Shopkeeper Business Mode</span>
                    </div>
                    ${subtitle ? `<p class="hidden sm:block text-[11.5px] truncate" style="color:var(--text-secondary);" id="ed-page-subtitle"></p>` : ''}
                </div>
            </div>

            <div class="flex items-center gap-2 md:gap-2.5 shrink-0">
                <!-- Two-Level Intelligence Switcher -->
                <div class="hidden sm:flex items-center p-0.5 rounded-lg border ed-rule" style="background:var(--bg-subtle);" role="group" aria-label="Intelligence Detail Level">
                    <button type="button" data-intel-choice="business" onclick="SmartStockEditorial.setIntelligenceMode('business')" class="ed-intel-btn px-2.5 py-1 rounded-md text-[11.5px] transition-all cursor-pointer">
                        Business
                    </button>
                    <button type="button" data-intel-choice="technical" onclick="SmartStockEditorial.setIntelligenceMode('technical')" class="ed-intel-btn px-2.5 py-1 rounded-md text-[11.5px] transition-all cursor-pointer">
                        Academic
                    </button>
                </div>

                <!-- Theme Toggle -->
                <button type="button" aria-label="Toggle Light or Dark theme" onclick="SmartStockEditorial.toggleTheme()"
                        class="h-9 px-2.5 rounded-lg border ed-rule flex items-center gap-1.5 text-xs font-medium cursor-pointer transition-colors"
                        style="background:var(--bg-subtle); color:var(--text-primary);">
                    <span class="material-symbols-outlined text-[18px] ed-theme-icon">dark_mode</span>
                    <span class="hidden md:inline ed-theme-label text-[11.5px]">Light</span>
                </button>

                <!-- Store Switcher Pill -->
                <button type="button" onclick="if(window.SmartStock) SmartStock.openStoreSwitcherModal()"
                        class="hidden md:flex h-9 px-3 rounded-lg border ed-rule items-center gap-1.5 text-xs font-semibold cursor-pointer"
                        style="background:var(--bg-canvas); color:var(--text-primary);">
                    <span class="w-1.5 h-1.5 rounded-full" style="background:var(--accent-primary);"></span>
                    <span class="store-pill-name max-w-[110px] truncate"></span>
                </button>

                <!-- Notifications -->
                <button type="button" aria-label="Notifications" onclick="if(window.SmartStock) SmartStock.openNotificationsModal()"
                        class="relative w-9 h-9 rounded-lg border ed-rule flex items-center justify-center cursor-pointer"
                        style="background:var(--bg-canvas); color:var(--text-primary);">
                    <span class="material-symbols-outlined text-[19px]">notifications</span>
                    <span class="header-notif-badge absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-tabular font-bold flex items-center justify-center"
                          style="background:var(--accent-secondary); color:#fff;">0</span>
                </button>

                <!-- Settings / Initial Avatar -->
                <a href="06_settings.html" aria-label="User Profile and Settings"
                   class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0 border ed-rule"
                   style="background:var(--accent-primary); color:var(--accent-primary-ink);" id="ed-header-avatar"></a>
            </div>
        `;

        const titleEl = header.querySelector('#ed-page-title');
        if (titleEl) titleEl.textContent = title;
        const subEl = header.querySelector('#ed-page-subtitle');
        if (subEl) subEl.textContent = subtitle;
        const pillName = header.querySelector('.store-pill-name');
        if (pillName) pillName.textContent = storeName;
        const avatarEl = header.querySelector('#ed-header-avatar');
        if (avatarEl) avatarEl.textContent = initial;

        // Mobile Bottom Quick Nav (< 1024px)
        const mobileNav = document.createElement('nav');
        mobileNav.id = 'ed-mobile-bottom-nav';
        mobileNav.className = 'lg:hidden fixed bottom-0 left-0 right-0 z-30 h-16 px-2 border-t ed-rule flex items-center justify-around';
        mobileNav.style.backgroundColor = 'var(--bg-surface)';
        const mobileLinks = [
            { id: 'overview', label: 'Home', icon: 'dashboard', href: '02_overview.html' },
            { id: 'inventory', label: 'Stock', icon: 'inventory_2', href: '03_inventory.html' },
            { id: 'sales', label: 'POS', icon: 'point_of_sale', href: '07_sales.html' },
            { id: 'forecasts', label: 'AI', icon: 'auto_awesome', href: '04_forecasts.html' },
            { id: 'assistant', label: 'Advisor', icon: 'smart_toy', href: '10_assistant.html' }
        ];
        mobileNav.innerHTML = mobileLinks.map(m => {
            const act = m.id === pageId;
            return `
                <a href="${m.href}" class="flex flex-col items-center justify-center gap-0.5 px-3 py-1 rounded-lg text-[10.5px] ${act ? 'font-bold' : 'font-medium'}"
                   style="${act ? 'color:var(--accent-primary);' : 'color:var(--text-secondary);'}">
                    <span class="material-symbols-outlined text-[20px]">${m.icon}</span>
                    <span>${m.label}</span>
                </a>
            `;
        }).join('');

        document.body.prepend(mobileNav);
        document.body.prepend(header);
        document.body.prepend(drawer);
        document.body.prepend(backdrop);

        // Apply active button styles
        applyTheme(getTheme());
        applyIntelligenceMode(getIntelligenceMode());
    }

    window.SmartStockEditorial = {
        renderShell,
        getTheme,
        applyTheme,
        toggleTheme,
        getIntelligenceMode,
        applyIntelligenceMode,
        setIntelligenceMode: applyIntelligenceMode,
        toggleDrawer
    };
})(window);

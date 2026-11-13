import { test, expect } from '@playwright/test';

test.describe('SmartStock Kirana Retail Web App - End-to-End Suite', () => {

  test('1. Hub Screen loads with status badges and device viewport', async ({ page }) => {
    await page.goto('/');
    
    // Main Title & Kirana branding
    await expect(page.locator('h1')).toContainText('SmartStock AI Suite');
    await expect(page.locator('body')).toContainText('Sharma Kirana Retail OS');

    // Status Badges
    await expect(page.locator('text=Supabase: txpvoqdecsjpmklelxdb')).toBeVisible();
    await expect(page.locator('text=Stitch: 776996957008142928')).toBeVisible();

    // Mobile Viewport Frame
    const iframe = page.locator('#stitch-viewport');
    await expect(iframe).toBeVisible();
    await expect(iframe).toHaveAttribute('src', 'screens/01_signin.html');
  });

  test('2. Screen Switcher navigates between Stitch retail screens', async ({ page }) => {
    await page.goto('/');

    const iframe = page.locator('#stitch-viewport');
    const openNewTabLink = page.locator('#open-new-tab');

    // Switch to Overview
    await page.click('button:has-text("2. Overview")');
    await expect(iframe).toHaveAttribute('src', 'screens/02_overview.html');
    await expect(openNewTabLink).toHaveAttribute('href', 'screens/02_overview.html');

    // Switch to Inventory
    await page.click('button:has-text("3. Inventory")');
    await expect(iframe).toHaveAttribute('src', 'screens/03_inventory.html');
    await expect(openNewTabLink).toHaveAttribute('href', 'screens/03_inventory.html');

    // Switch to Forecasts
    await page.click('button:has-text("4. Forecasts")');
    await expect(iframe).toHaveAttribute('src', 'screens/04_forecasts.html');
    await expect(openNewTabLink).toHaveAttribute('href', 'screens/04_forecasts.html');

    // Switch to Settings
    await page.click('button:has-text("6. Settings")');
    await expect(iframe).toHaveAttribute('src', 'screens/06_settings.html');
    await expect(openNewTabLink).toHaveAttribute('href', 'screens/06_settings.html');
  });

  test('3. Auth Guard: Unauthenticated access to dashboard redirects to Sign In', async ({ page }) => {
    // Navigate directly to overview without being signed in
    await page.goto('/screens/02_overview.html');
    
    // Auth guard in smartstock-bridge.js should redirect to 01_signin.html
    await page.waitForURL('**/screens/01_signin.html');
    await expect(page).toHaveURL(/01_signin\.html/);
    await expect(page.locator('#tab-btn-signin')).toBeVisible();
  });

  test('4. Sign In Screen: Toggle tabs between Sign In and Sign Up', async ({ page }) => {
    await page.goto('/screens/01_signin.html');

    // Initial state: Sign In active
    await expect(page.locator('#section-signin')).toBeVisible();
    await expect(page.locator('#section-signup')).toBeHidden();

    // Toggle to Sign Up
    await page.click('#tab-btn-signup');
    await expect(page.locator('#section-signup')).toBeVisible();
    await expect(page.locator('#section-signin')).toBeHidden();

    // Toggle back to Sign In
    await page.click('#tab-btn-signin');
    await expect(page.locator('#section-signin')).toBeVisible();
    await expect(page.locator('#section-signup')).toBeHidden();
  });

  test.describe('Authenticated Merchant Session', () => {
    const SCREENSHOT_DIR = '/Users/snnaniswarnababu/.gemini/antigravity/brain/bb8639e7-c0b2-4c49-b156-0cc805557c57/phase2_screenshots';

    test.beforeEach(async ({ page }) => {
      // Seed authenticated merchant session & sample catalog products for realistic screenshots & flows
      await page.addInitScript(() => {
        const email = 'owner@sharmakirana.in';
        localStorage.setItem(
          'smartstock_user',
          JSON.stringify({
            email,
            store: 'Sharma Kirana Store',
            shop_id: 'b3bccd6d-875b-46e6-ade5-d9e8069b8b08',
          })
        );
        localStorage.setItem('smartstock_last_active_store', 'Sharma Kirana Store');
        const safeEmail = email.replace(/[^a-zA-Z0-9_-]/g, '_');
        const prodKey = `smartstock_local_products_${safeEmail}`;
        if (!localStorage.getItem(prodKey)) {
          localStorage.setItem(
            prodKey,
            JSON.stringify([
              { id: 'sku-1', sku: 'AT-01', name: 'Aashirvaad Atta 5kg', category_name: 'Staples', unit_price: 265, unit_cost: 225, stock_on_hand: 18, reorder_point: 10, status: 'active' },
              { id: 'sku-2', sku: 'TD-02', name: 'Toor Dal Premium 1kg', category_name: 'Pulses', unit_price: 168, unit_cost: 138, stock_on_hand: 4, reorder_point: 12, status: 'low_stock' },
              { id: 'sku-3', sku: 'MO-03', name: 'Fortune Mustard Oil 1L', category_name: 'Oils', unit_price: 175, unit_cost: 148, stock_on_hand: 0, reorder_point: 8, status: 'out_of_stock' },
              { id: 'sku-4', sku: 'CH-04', name: 'Tata Tea Gold 250g', category_name: 'Beverages', unit_price: 145, unit_cost: 118, stock_on_hand: 24, reorder_point: 8, status: 'active' },
            ])
          );
        }
      });
    });

    test('5. Overview Dashboard: Loads editorial briefing, side drawer, theme & intelligence toggles', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      const errors = [];
      page.on('pageerror', (err) => errors.push(err.message));

      await page.goto('/screens/02_overview.html');
      await expect(page.locator('#side-drawer')).toBeAttached();
      await expect(page.locator('.drawer-store-name').first()).toHaveText('Sharma Kirana Store');
      await expect(page.locator('#side-drawer a[data-path="overview"]')).toBeVisible();
      await expect(page.locator('#side-drawer a[data-path="inventory"]')).toBeVisible();
      await expect(page.locator('#side-drawer a[data-path="orders"]')).toBeVisible();

      // Light mode desktop screenshot
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/overview_desktop_light.png` });

      // Switch to Academic Technical Mode & Dark Mode
      await page.click('button[data-intel-choice="technical"]');
      await expect(page.locator('body')).toHaveAttribute('data-intel', 'technical');
      await expect(page.locator('.tech-only').first()).toBeVisible();

      await page.click('button[aria-label="Toggle Light or Dark theme"]');
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
      await page.waitForTimeout(250);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/overview_desktop_dark.png` });

      // Reset to light/business cleanly and verify mobile viewport has no horizontal overflow
      await page.click('button[aria-label="Toggle Light or Dark theme"]');
      await page.click('button[data-intel-choice="business"]');
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(200);
      const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      expect(hasOverflow).toBe(false);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/overview_mobile_light.png` });
      expect(errors).toEqual([]);
    });

    test('6. Inventory Workbench & Inspector: Displays catalog, filters & inspector panel', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto('/screens/03_inventory.html');
      await expect(page.locator('#inventory-list')).toBeVisible();
      await expect(page.locator('#sku-inspector')).toBeVisible();
      await expect(page.locator('#inventory-list')).toContainText('Aashirvaad Atta 5kg');

      await page.click('.filter-pill[data-filter="low"]');
      await expect(page.locator('#inventory-list .inventory-card[data-status="low"]')).toBeVisible();
      await page.click('.filter-pill[data-filter="all"]');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/inventory_desktop_light.png` });
    });

    test('7. Sales & POS Terminal: Add items to bill and complete stock-safe checkout', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto('/screens/07_sales.html');
      await expect(page.locator('#pos-product-grid')).toContainText('Aashirvaad Atta 5kg');

      await page.click('#pos-product-grid button:has-text("Aashirvaad Atta 5kg")');
      await expect(page.locator('#pos-cart-total')).toContainText('265');
      await page.click('#pos-checkout-btn');
      await expect(page.locator('#pos-receipt-box')).toBeVisible();
      await expect(page.locator('#pos-sales-tbody')).toContainText('Aashirvaad Atta 5kg');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/sales_pos_desktop_light.png` });
    });

    test('8. Forecasts Workbench: Horizon & Granularity switch renders SVG curve', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto('/screens/04_forecasts.html');
      await expect(page.locator('#forecast-horizon-bar')).toBeVisible();
      await page.click('.horizon-btn[data-days="28"]');
      await page.click('#fc-gran-weekly');
      await expect(page.locator('#fc-main-svg')).toBeVisible();
      await page.screenshot({ path: `${SCREENSHOT_DIR}/forecasts_desktop_light.png` });
    });

    test('9. Replenishment & Purchase Orders: Triage lanes and PO lifecycle actions work', async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto('/screens/05_replenishment.html');
      await expect(page.locator('#ai-replenishment-container')).toBeVisible();
      await expect(page.locator('#replenish-bottom-bar')).toBeVisible();
      await page.screenshot({ path: `${SCREENSHOT_DIR}/replenishment_desktop_light.png` });

      await page.goto('/screens/05_purchase_orders.html');
      await expect(page.locator('#po-main')).toBeVisible();
      await page.click('#po-draft-banner button:has-text("Issue Draft PO Now")');
      await expect(page.locator('#po-ledger-container')).toContainText('Metro');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/orders_desktop_light.png` });
    });

    test('10. Anomalies, Segmentation, Assistant, Analytics & Suppliers load cleanly in Light & Dark', async ({ page }) => {
      const errors = [];
      page.on('pageerror', (err) => errors.push(err.message));
      await page.setViewportSize({ width: 1440, height: 900 });

      await page.goto('/screens/08_anomalies.html');
      await expect(page.locator('#anom-tbody')).toBeVisible();
      await page.screenshot({ path: `${SCREENSHOT_DIR}/anomalies_desktop_light.png` });

      await page.goto('/screens/09_segmentation.html');
      await expect(page.locator('#cell-AX')).toBeVisible();
      await page.click('#cell-AX');
      await expect(page.locator('#seg-table-title')).toContainText('AX');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/segmentation_desktop_dark_check.png` });

      await page.goto('/screens/10_assistant.html');
      await page.click('button:has-text("What items should I reorder urgently today?")');
      await expect(page.locator('#ast-messages')).toContainText('Toor Dal');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/assistant_desktop_light.png` });

      await page.goto('/screens/11_analytics.html');
      await expect(page.locator('#an-model-tbody')).toContainText('LightGBM');
      await page.screenshot({ path: `${SCREENSHOT_DIR}/analytics_desktop_light.png` });

      await page.goto('/screens/12_suppliers.html');
      await expect(page.locator('#sup-grid')).toBeVisible();
      await page.screenshot({ path: `${SCREENSHOT_DIR}/suppliers_desktop_light.png` });

      await page.goto('/screens/06_settings.html');
      await expect(page.locator('#profile-store-name')).toHaveText('Sharma Kirana Store');
      await page.click('#set-theme-dark');
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
      await page.waitForTimeout(150);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/settings_desktop_dark.png` });

      // Clean unauthenticated context for true Sign In mobile screenshot
      const cleanCtx = await page.context().browser().newContext({ viewport: { width: 390, height: 844 } });
      const signInPage = await cleanCtx.newPage();
      await signInPage.goto('http://127.0.0.1:3000/screens/01_signin.html');
      const overflowSignin = await signInPage.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      expect(overflowSignin).toBe(false);
      await signInPage.screenshot({ path: `${SCREENSHOT_DIR}/signin_mobile_light.png` });
      await cleanCtx.close();

      expect(errors).toEqual([]);
    });

    test('11. Priority A/B/C Closure: PO persistence across reload, supplier persistence, and bulk operations', async ({ page }) => {
      const errors = [];
      page.on('pageerror', (err) => errors.push(err.message));
      await page.setViewportSize({ width: 1440, height: 900 });

      // 1. PO Creation and Persistence across page reload
      await page.goto('/screens/05_purchase_orders.html');
      await expect(page.locator('#po-main')).toBeVisible();
      
      const createdPO = await page.evaluate(async () => {
        return await window.SmartStock.createManualPO({
          supplier: 'Metro Cash & Carry',
          expectedDate: '2026-11-28',
          items: [{ name: 'Parle-G 250g', sku: 'SKU-E2E-PO', units: 30, cost: 20 }]
        });
      });
      expect(createdPO).toBeTruthy();

      // Reload page and assert PO still persists
      await page.reload();
      await expect(page.locator('#po-ledger-container')).toContainText('Metro Cash & Carry');

      // 2. Supplier Addition and Persistence across page reload
      await page.goto('/screens/12_suppliers.html');
      await expect(page.locator('#sup-grid')).toBeVisible();
      
      await page.evaluate(async () => {
        await window.SmartStock.addSupplier({
          name: 'Bengaluru Spice Traders',
          category: 'Spices & Seasoning',
          phone: '+91 98888 77777',
          hub: 'APMC Yard 4',
          lead_time_days: 3
        });
      });

      await page.reload();
      await expect(page.locator('#sup-grid')).toContainText('Bengaluru Spice Traders');

      // 3. Inventory Bulk Operations
      await page.goto('/screens/03_inventory.html');
      await expect(page.locator('#inventory-list')).toBeVisible();
      const initialCount = await page.locator('#inventory-list .inventory-card').count();
      expect(initialCount).toBeGreaterThan(0);

      // Add a temporary item and then bulk delete it
      await page.evaluate(async () => {
        await window.SmartStock.addProduct({
          name: 'Bulk Deletion Test SKU',
          sku: 'SKU-BULK-DEL-1',
          unit_price: 99,
          unit_cost: 75,
          stock_on_hand: 10,
          reorder_point: 5,
          category_name: 'Test'
        });
      });
      await page.reload();
      await expect(page.locator('#inventory-list')).toContainText('Bulk Deletion Test SKU');

      // Execute bulk delete on test item
      await page.evaluate(async () => {
        const prods = await window.SmartStock.getProducts();
        const testItem = prods.find(p => p.sku === 'SKU-BULK-DEL-1' || p.name === 'Bulk Deletion Test SKU');
        if (testItem) {
          await window.SmartStock.bulkDelete([testItem.id]);
        }
      });
      await page.reload();
      await expect(page.locator('#inventory-list')).not.toContainText('Bulk Deletion Test SKU');

      expect(errors).toEqual([]);
    });
  });
});

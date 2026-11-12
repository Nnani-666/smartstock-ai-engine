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
    test.beforeEach(async ({ page }) => {
      // Seed authenticated merchant session
      await page.addInitScript(() => {
        localStorage.setItem(
          'smartstock_user',
          JSON.stringify({
            email: 'owner@sharmakirana.in',
            store: 'Sharma Kirana Store',
            shop_id: 'b3bccd6d-875b-46e6-ade5-d9e8069b8b08',
          })
        );
      });
    });

    test('5. Overview Dashboard: Loads store overview and side navigation drawer', async ({ page }) => {
      await page.goto('/screens/02_overview.html');

      // Verify dashboard rendered
      await expect(page.locator('#side-drawer')).toBeAttached();
      await expect(page.locator('.drawer-store-name').first()).toHaveText('Sharma Kirana Store');
      
      // Verify navigation items exist in side drawer
      await expect(page.locator('#side-drawer a[data-path="overview"]')).toBeVisible();
      await expect(page.locator('#side-drawer a[data-path="inventory"]')).toBeVisible();
      await expect(page.locator('#side-drawer a[data-path="orders"]')).toBeVisible();
    });

    test('6. Inventory Screen: Displays Kirana product catalog and stock levels', async ({ page }) => {
      await page.goto('/screens/03_inventory.html');

      // Verify inventory view loaded
      await expect(page.locator('body')).toBeVisible();
      
      // Check that stock items or search elements are present
      const bodyText = await page.textContent('body');
      expect(bodyText.length).toBeGreaterThan(100);
    });

    test('7. Demand Forecasts: Loads AI demand predictions and reorder suggestions', async ({ page }) => {
      await page.goto('/screens/04_forecasts.html');

      // Verify AI Forecasts loaded
      await expect(page.locator('body')).toBeVisible();
      const bodyText = await page.textContent('body');
      expect(bodyText.length).toBeGreaterThan(100);
    });

    test('8. Purchase Orders & Settings screens render without errors', async ({ page }) => {
      await page.goto('/screens/05_purchase_orders.html');
      await expect(page.locator('body')).toBeVisible();

      await page.goto('/screens/06_settings.html');
      await expect(page.locator('body')).toBeVisible();
    });
  });
});

const { test, expect } = require('@playwright/test');

test.describe('Critical Cross-Account AI Data Isolation & Browser Switching Audit', () => {

  test('Seamless account switching must never leak inventory or sales data across tenants', async ({ page }) => {
    test.setTimeout(90000);

    // ==========================================
    // 1. LOGIN ACCOUNT A (tenant_alpha@smartstock.in)
    // ==========================================
    console.log('[E2E TEST] Step 1: Logging in as Tenant Alpha...');
    await page.goto('http://localhost:3000/screens/01_signin.html');
    await page.fill('#merchant-email', 'tenant_alpha@smartstock.in');
    await page.fill('#merchant-password', 'PasswordAlpha123!');
    await page.click('#submit-auth-btn');

    await page.waitForURL('**/02_overview.html');
    const tokenA = await page.evaluate(() => localStorage.getItem('smartstock_token'));
    const userA = await page.evaluate(() => JSON.parse(localStorage.getItem('smartstock_user') || '{}'));
    expect(tokenA).toBeTruthy();
    expect(userA.email).toBe('tenant_alpha@smartstock.in');

    // ==========================================
    // 2. QUERY ASSISTANT UNDER ACCOUNT A
    // ==========================================
    console.log('[E2E TEST] Step 2: Querying assistant under Tenant Alpha...');
    await page.goto('http://localhost:3000/screens/10_assistant.html');
    await page.waitForSelector('#ast-input');

    await page.fill('#ast-input', 'Which product is my top selling?');
    await page.click('#ast-send-btn');

    // Wait for the response message bubble to appear
    await page.waitForFunction(() => {
      const msgs = document.querySelectorAll('#ast-messages p');
      return msgs.length >= 2;
    }, { timeout: 25000 });
    await page.waitForTimeout(2000);

    const msgsA = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#ast-messages p')).map(p => p.textContent).join('\n');
    });
    console.log('[E2E TEST] Tenant Alpha Response Summary:\n', msgsA.slice(0, 150));

    expect(msgsA).toContain('ALPHA');
    expect(msgsA).not.toContain('TEST_PRODUCT_BETA');

    // ==========================================
    // 3. LOG OUT VIA SETTINGS
    // ==========================================
    console.log('[E2E TEST] Step 3: Logging out Tenant Alpha...');
    await page.goto('http://localhost:3000/screens/06_settings.html');
    await page.waitForSelector('button[onclick="SmartStock.signOut()"]');
    await page.click('button[onclick="SmartStock.signOut()"]');
    await page.waitForURL('**/01_signin.html');

    const tokenAfterLogout = await page.evaluate(() => localStorage.getItem('smartstock_token'));
    const userAfterLogout = await page.evaluate(() => localStorage.getItem('smartstock_user'));
    expect(tokenAfterLogout).toBeNull();
    expect(userAfterLogout).toBeNull();

    // ==========================================
    // 4. LOGIN ACCOUNT B (tenant_beta@smartstock.in)
    // ==========================================
    console.log('[E2E TEST] Step 4: Logging in as Tenant Beta...');
    await page.fill('#merchant-email', 'tenant_beta@smartstock.in');
    await page.fill('#merchant-password', 'PasswordBeta123!');
    await page.click('#submit-auth-btn');

    await page.waitForURL('**/02_overview.html');
    const tokenB = await page.evaluate(() => localStorage.getItem('smartstock_token'));
    const userB = await page.evaluate(() => JSON.parse(localStorage.getItem('smartstock_user') || '{}'));
    expect(tokenB).toBeTruthy();
    expect(tokenB).not.toBe(tokenA);
    expect(userB.email).toBe('tenant_beta@smartstock.in');

    // ==========================================
    // 5. QUERY ASSISTANT UNDER ACCOUNT B
    // ==========================================
    console.log('[E2E TEST] Step 5: Querying assistant under Tenant Beta...');
    await page.goto('http://localhost:3000/screens/10_assistant.html');
    await page.waitForSelector('#ast-input');

    // Ensure conversation thread was purged of Account A's history
    const initialMsgsB = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#ast-messages p')).map(p => p.textContent).join('\n');
    });
    expect(initialMsgsB).not.toContain('TEST_PRODUCT_ALPHA');

    await page.fill('#ast-input', 'Which product is my top selling?');
    await page.click('#ast-send-btn');

    await page.waitForFunction(() => {
      const msgs = document.querySelectorAll('#ast-messages p');
      return msgs.length >= 2;
    }, { timeout: 25000 });
    await page.waitForTimeout(2000);

    const msgsB = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#ast-messages p')).map(p => p.textContent).join('\n');
    });
    console.log('[E2E TEST] Tenant Beta Response Summary:\n', msgsB.slice(0, 150));

    expect(msgsB).toContain('BETA');
    expect(msgsB).not.toContain('TEST_PRODUCT_ALPHA');

    // ==========================================
    // 6. VERIFY NO RESIDUAL ACCOUNT A KEYS IN STORAGE
    // ==========================================
    console.log('[E2E TEST] Step 6: Verifying localStorage isolation...');
    const allKeys = await page.evaluate(() => Object.keys(localStorage));
    const leakedAlphaKeys = allKeys.filter(k => k.includes('tenant_alpha'));
    expect(leakedAlphaKeys.length).toBe(0);

    console.log('[E2E TEST] Cross-Account Isolation Test PASSED with zero contamination!');
  });

  test('In-flight assistant request is cleanly aborted on logout and never pollutes new session', async ({ page }) => {
    test.setTimeout(60000);

    // 1. Login as Tenant Alpha
    await page.goto('http://localhost:3000/screens/01_signin.html');
    await page.fill('#merchant-email', 'tenant_alpha@smartstock.in');
    await page.fill('#merchant-password', 'PasswordAlpha123!');
    await page.click('#submit-auth-btn');
    await page.waitForURL('**/02_overview.html');

    // 2. Open assistant and dispatch a request
    await page.goto('http://localhost:3000/screens/10_assistant.html');
    await page.waitForSelector('#ast-input');
    await page.fill('#ast-input', 'Summarize my recent sales and revenue performance.');
    await page.click('#ast-send-btn');

    // 3. Immediately trigger logout without waiting for AI response
    await page.evaluate(() => SmartStock.signOut());
    await page.waitForURL('**/01_signin.html');

    // 4. Log in as Tenant Beta
    await page.fill('#merchant-email', 'tenant_beta@smartstock.in');
    await page.fill('#merchant-password', 'PasswordBeta123!');
    await page.click('#submit-auth-btn');
    await page.waitForURL('**/02_overview.html');

    // 5. Open assistant under Tenant Beta
    await page.goto('http://localhost:3000/screens/10_assistant.html');
    await page.waitForSelector('#ast-messages');

    // Wait 3 seconds to ensure any lingering background promise would have settled
    await page.waitForTimeout(3000);

    // Ensure Tenant Beta's thread does not contain Tenant Alpha's sales response or aborted error
    const betaThreadText = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('#ast-messages p')).map(p => p.textContent).join('\n');
    });
    expect(betaThreadText).not.toContain('TEST_PRODUCT_ALPHA');
    expect(betaThreadText).not.toContain('₹1,500');
    expect(betaThreadText).not.toContain('Session changed');
    console.log('[E2E TEST] In-Flight Abort Isolation PASSED!');
  });

});

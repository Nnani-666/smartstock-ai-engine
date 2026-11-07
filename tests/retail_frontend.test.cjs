/**
 * Retail Frontend & Bridge Test Suite
 * 17 Comprehensive Unit Tests for SmartStock Kirana Retail Engine
 */

const test = require('node:test');
const assert = require('node:assert');

function createMockStorage() {
    let store = {};
    return {
        getItem(k) { return store.hasOwnProperty(k) ? store[k] : null; },
        setItem(k, v) { store[k] = String(v); },
        removeItem(k) { delete store[k]; },
        clear() { store = {}; }
    };
}

global.localStorage = createMockStorage();
global.window = global;
global.fetch = async () => ({ ok: true, json: async () => [] });

const SmartStock = require('../stitch/smartstock-bridge.js');

function setupTestUser(email = 'owner@sharmakirana.in') {
    global.localStorage.clear();
    global.localStorage.setItem('smartstock_user', JSON.stringify({ email, store: 'Sharma Kirana Store' }));
}

test('1. Daily revenue sums only today transactions in Asia/Kolkata', () => {
    setupTestUser();
    const todayStr = SmartStock.getBusinessDate();
    const yesterdayStr = SmartStock.getBusinessDate(new Date(Date.now() - 86400000));

    const sales = [
        { id: 's1', productId: 'p1', name: 'Item 1', qty: 2, unit_price: 75, total: 150, date: todayStr },
        { id: 's2', productId: 'p2', name: 'Item 2', qty: 1, unit_price: 200, total: 200, date: yesterdayStr },
        { id: 's3', productId: 'p3', name: 'Item 3', qty: 1, unit_price: 300, total: 300, date: '2026-01-01' }
    ];
    SmartStock.saveSales(sales);

    const summary = SmartStock.getSalesSummary('Today (Live)');
    assert.strictEqual(summary.count, 1, 'Only today sale should be included');
    assert.strictEqual(summary.revenue, 150, 'Daily revenue must equal sum of today transactions');
    assert.strictEqual(summary.totalUnits, 2, 'Total units should match today sale');
});

test('2. Rolling date filtering (Today, Last 7 Days, Last 30 Days, This Month, All Time)', () => {
    setupTestUser();
    const today = new Date();
    const dStr = (daysAgo) => {
        const d = new Date(today.getTime() - daysAgo * 86400000);
        return SmartStock.getBusinessDate(d);
    };

    const sales = [
        { id: 's0', date: dStr(0), qty: 1, unit_price: 10 },   // today
        { id: 's3', date: dStr(3), qty: 1, unit_price: 20 },   // 3 days ago
        { id: 's10', date: dStr(10), qty: 1, unit_price: 30 }, // 10 days ago
        { id: 's25', date: dStr(25), qty: 1, unit_price: 40 }, // 25 days ago
        { id: 's60', date: dStr(60), qty: 1, unit_price: 50 }  // 60 days ago
    ];
    SmartStock.saveSales(sales);

    const todaySales = SmartStock.getFilteredSales('Today (Live)');
    assert.strictEqual(todaySales.length, 1);
    assert.strictEqual(todaySales[0].id, 's0');

    const last7 = SmartStock.getFilteredSales('Last 7 Days');
    assert.strictEqual(last7.length, 2); // s0 and s3

    const last30 = SmartStock.getFilteredSales('Last 30 Days');
    assert.strictEqual(last30.length, 4); // s0, s3, s10, s25

    const allTime = SmartStock.getFilteredSales('All Time');
    assert.strictEqual(allTime.length, 5);
});

test('3. Historical sale entries with custom date/timestamp', async () => {
    setupTestUser();
    const prod = {
        id: 'prod-hist-1',
        name: 'Turmeric Powder (500g)',
        stock_on_hand: 20,
        unit_price: 80,
        unit_cost: 60,
        reorder_point: 5
    };
    SmartStock.saveProducts([prod]);

    const customDate = '2026-10-15';
    const customTimestamp = '2026-10-15T10:30:00.000Z';
    const updated = await SmartStock.updateStock(prod.id, -3, {
        date: customDate,
        timestamp: customTimestamp
    });

    assert.strictEqual(updated.stock_on_hand, 17);
    const sales = SmartStock.getSales();
    assert.strictEqual(sales.length, 1);
    assert.strictEqual(sales[0].date, customDate);
    assert.strictEqual(sales[0].timestamp, customTimestamp);
    assert.strictEqual(sales[0].qty, 3);
});

test('4. Gross profit calculated using unit cost', () => {
    setupTestUser();
    const todayStr = SmartStock.getBusinessDate();
    const sales = [
        { id: 's1', date: todayStr, qty: 3, unit_price: 100, unit_cost: 70 }, // Rev: 300, Cost: 210, Profit: 90
        { id: 's2', date: todayStr, qty: 2, unit_price: 50, unit_cost: 30 }   // Rev: 100, Cost: 60, Profit: 40
    ];
    SmartStock.saveSales(sales);

    const summary = SmartStock.getSalesSummary('Today (Live)');
    assert.strictEqual(summary.revenue, 400);
    assert.strictEqual(summary.cost, 270);
    assert.strictEqual(summary.grossProfit, 130);
    assert.strictEqual(summary.costAvailable, true);
    assert.strictEqual(Math.round(summary.grossMargin * 10) / 10, 32.5);
});

test('5. Legacy profit shows unavailable when unit cost is missing', () => {
    setupTestUser();
    const todayStr = SmartStock.getBusinessDate();
    const sales = [
        { id: 's1', date: todayStr, qty: 2, unit_price: 100, unit_cost: 60 },
        { id: 's2', date: todayStr, qty: 1, unit_price: 120, unit_cost: null } // missing historical cost
    ];
    SmartStock.saveSales(sales);

    const summary = SmartStock.getSalesSummary('Today (Live)');
    assert.strictEqual(summary.revenue, 320);
    assert.strictEqual(summary.costAvailable, false, 'Should flag cost as unavailable');
    assert.strictEqual(summary.cost, null);
    assert.strictEqual(summary.grossProfit, null);
    assert.strictEqual(summary.grossMargin, null);
});

test('6. Sales form uses unified stock routine and does not call adjustStock', async () => {
    setupTestUser();
    const prod = {
        id: 'prod-form-test',
        name: 'Parle-G Glucose Biscuits',
        stock_on_hand: 25,
        unit_price: 10,
        unit_cost: 7,
        reorder_point: 5
    };
    SmartStock.saveProducts([prod]);

    // Mock minimal DOM for modal submission
    const mockElements = {
        'sale-record-product-select': { value: prod.id },
        'sale-record-qty-input': { value: '4' },
        'sale-record-date-input': { value: '2026-10-20' }
    };
    global.document = {
        getElementById: (id) => mockElements[id] || null,
        querySelectorAll: () => []
    };

    let updateStockCalled = false;
    const origUpdateStock = SmartStock.updateStock;
    SmartStock.updateStock = async function(id, delta, opts) {
        updateStockCalled = true;
        assert.strictEqual(id, prod.id);
        assert.strictEqual(delta, -4);
        return origUpdateStock.call(this, id, delta, opts);
    };

    try {
        await SmartStock.recordNewSaleFromModal({ preventDefault() {} });
        assert.strictEqual(updateStockCalled, true, 'recordNewSaleFromModal must route through updateStock');
        const updated = (await SmartStock.getProducts()).find(p => p.id === prod.id);
        assert.strictEqual(updated.stock_on_hand, 21);
    } finally {
        SmartStock.updateStock = origUpdateStock;
        delete global.document;
    }
});

test('7. Sales history retained without 50-item limit', async () => {
    setupTestUser();
    const prod = { id: 'prod-limit-test', name: 'Sugar 1kg', stock_on_hand: 500, unit_price: 45, unit_cost: 38, reorder_point: 10 };
    SmartStock.saveProducts([prod]);

    const batchSales = [];
    for (let i = 1; i <= 75; i++) {
        batchSales.push({
            id: `sale-${i}`,
            productId: prod.id,
            name: prod.name,
            qty: 1,
            unit_price: 45,
            unit_cost: 38,
            total: 45,
            date: '2026-10-01',
            timestamp: new Date().toISOString()
        });
    }
    SmartStock.saveSales(batchSales);

    // Add one more via updateStock
    await SmartStock.updateStock(prod.id, -1);
    const recordedSales = SmartStock.getSales();
    assert.strictEqual(recordedSales.length, 76, 'All 76 sales must be retained without 50-item truncation');
});

test('8. Stock mutations serialized against rapid taps', async () => {
    setupTestUser();
    const prod = { id: 'prod-rapid-tap', name: 'Maggi 2-Min Noodles', stock_on_hand: 20, unit_price: 14, unit_cost: 11, reorder_point: 5 };
    SmartStock.saveProducts([prod]);

    // Dispatch 5 concurrent sales in parallel
    const promises = [
        SmartStock.updateStock(prod.id, -1),
        SmartStock.updateStock(prod.id, -1),
        SmartStock.updateStock(prod.id, -1),
        SmartStock.updateStock(prod.id, -1),
        SmartStock.updateStock(prod.id, -1)
    ];

    await Promise.all(promises);
    const updated = (await SmartStock.getProducts()).find(p => p.id === prod.id);
    assert.strictEqual(updated.stock_on_hand, 15, 'Serialized mutations must decrement accurately without race conditions');
});

test('9. Overselling rejected completely', async () => {
    setupTestUser();
    const prod = { id: 'prod-oversell', name: 'Sunflower Cooking Oil (1L)', stock_on_hand: 4, unit_price: 140, unit_cost: 115, reorder_point: 2 };
    SmartStock.saveProducts([prod]);

    const result = await SmartStock.updateStock(prod.id, -6); // Requested 6, only 4 on hand
    assert.strictEqual(result, null, 'Oversell attempt must return null and be rejected');

    const checkProd = (await SmartStock.getProducts()).find(p => p.id === prod.id);
    assert.strictEqual(checkProd.stock_on_hand, 4, 'Stock on hand must remain completely unchanged');
    assert.strictEqual(SmartStock.getSales().length, 0, 'No sale record should be saved');
});

test('10. Zero prices preserved', async () => {
    setupTestUser();
    const prod = { id: 'prod-free-sample', name: 'Promotion Complimentary Sample', stock_on_hand: 10, unit_price: 0, unit_cost: 0, reorder_point: 2 };
    SmartStock.saveProducts([prod]);

    const updated = await SmartStock.updateStock(prod.id, -2);
    assert.strictEqual(updated.stock_on_hand, 8);

    const sales = SmartStock.getSales();
    assert.strictEqual(sales.length, 1);
    assert.strictEqual(sales[0].unit_price, 0, 'Zero unit price must be preserved and not replaced by default 50');
    assert.strictEqual(sales[0].total, 0, 'Zero total amount must be preserved');
});

test('11. Currency math in integer paise without floating point error', () => {
    assert.strictEqual(SmartStock.toPaise(19.99), 1999);
    assert.strictEqual(SmartStock.fromPaise(1999), 19.99);

    // Standard JavaScript float error test: 0.1 + 0.2 === 0.30000000000000004
    const floatSum = 0.1 + 0.2;
    assert.notStrictEqual(floatSum, 0.3); // Demonstrates float flaw

    // Integer paise math avoids the float flaw:
    const preciseSum = SmartStock.fromPaise(SmartStock.toPaise(0.1) + SmartStock.toPaise(0.2));
    assert.strictEqual(preciseSum, 0.3, 'Integer paise math must eliminate precision errors');
});

test('12. Inventory valuation uses purchase cost', () => {
    const products = [
        { stock_on_hand: 10, unit_cost: 45.0, unit_price: 60.0 }, // 10 * 45 = 450
        { stock_on_hand: 20, unit_cost: 80.0, unit_price: 110.0 }, // 20 * 80 = 1600
        { stock_on_hand: 5, unit_cost: 12.5, unit_price: 20.0 }   // 5 * 12.5 = 62.5
    ];

    const val = SmartStock.getInventoryValuation(products);
    assert.strictEqual(val, 2112.5, 'Inventory valuation must strictly use unit_cost (purchase cost basis)');
});

test('13. Merchant reorder points (including 0 and > 30) preserved', async () => {
    setupTestUser();
    const products = [
        { id: 'p-zero', name: 'Zero ROP Item', stock_on_hand: 15, reorder_point: 0 },
        { id: 'p-high', name: 'High Threshold Wholesale', stock_on_hand: 120, reorder_point: 85 }
    ];
    SmartStock.saveProducts(products);

    const loaded = await SmartStock.getProducts();
    const pZero = loaded.find(p => p.id === 'p-zero');
    const pHigh = loaded.find(p => p.id === 'p-high');

    assert.strictEqual(pZero.reorder_point, 0, 'Reorder point 0 must be preserved');
    assert.strictEqual(pHigh.reorder_point, 85, 'Reorder point > 30 must not be clamped');
});

test('14. Actual demand chart aggregates actual sale quantities', () => {
    // 2026-10-19 is Monday (UTC)
    // 2026-10-23 is Friday (UTC)
    // 2026-10-24 is Saturday (UTC)
    const sales = [
        { date: '2026-10-19', qty: 7 }, // Monday
        { date: '2026-10-19', qty: 3 }, // Monday (+3 = 10)
        { date: '2026-10-23', qty: 15 }, // Friday
        { date: '2026-10-24', qty: 22 }  // Saturday
    ];

    const { days, actuals } = SmartStock.calculateDayOfWeekDemand(sales);
    assert.deepStrictEqual(days, ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
    assert.strictEqual(actuals[0], 10, 'Monday should aggregate 10 units');
    assert.strictEqual(actuals[1], 0, 'Tuesday should have 0 units');
    assert.strictEqual(actuals[4], 15, 'Friday should aggregate 15 units');
    assert.strictEqual(actuals[5], 22, 'Saturday should aggregate 22 units');
});

test('15. Forecast calculates completed-day average with zero-sale days included', () => {
    // Reference date: 2026-10-25 (Sunday)
    // 7 completed days: Oct 18, 19, 20, 21, 22, 23, 24
    // Suppose sales occurred only on Oct 19 (10 units) and Oct 23 (11 units). Total = 21 units.
    // Average over 7 days = 21 / 7 = 3.0 units/day (zero-sale days included in denominator)
    const sales = [
        { date: '2026-10-19', qty: 10 },
        { date: '2026-10-23', qty: 11 },
        { date: '2026-10-25', qty: 50 } // Today (not a completed day, must NOT be in completed days average)
    ];

    const result = SmartStock.calculateCompletedDayAverage(sales, 7, '2026-10-25');
    assert.strictEqual(result.numDays, 7);
    assert.strictEqual(result.totalUnits, 21, 'Total units over completed days window');
    assert.strictEqual(result.average, 3.0, 'Average must divide by 7 including the 5 zero-sale days');
});

test('16. Purchase receipts are idempotent and reject invalid/cancelled orders', async () => {
    setupTestUser();
    const prod = { id: 'p-po-item', name: 'Basmati Rice (5kg)', stock_on_hand: 10, stock_on_order: 25, reorder_point: 8 };
    SmartStock.saveProducts([prod]);

    // 1. Rejection of cancelled order
    const cancelledPO = {
        id: 'po-cancel-test',
        po_number: 'PO-2026-001',
        status: 'cancelled',
        items: [{ product_id: prod.id, units: 25 }]
    };
    SmartStock.savePurchaseOrders([cancelledPO]);

    const cancelRes = await SmartStock.receivePO(cancelledPO.id);
    assert.strictEqual(cancelRes.success, false, 'Cannot receive cancelled PO');

    // 2. Receipt with invalid units skipped
    const validPO = {
        id: 'po-valid-test',
        po_number: 'PO-2026-002',
        status: 'ordered',
        items: [
            { product_id: prod.id, units: 20 },
            { product_id: prod.id, units: -5 } // negative units skipped
        ]
    };
    SmartStock.savePurchaseOrders([validPO]);

    const receiveRes1 = await SmartStock.receivePO(validPO.id);
    assert.strictEqual(receiveRes1.success, true);
    assert.strictEqual(receiveRes1.totalUnitsReceived, 20);

    const afterFirst = (await SmartStock.getProducts()).find(p => p.id === prod.id);
    assert.strictEqual(afterFirst.stock_on_hand, 30); // 10 + 20

    // 3. Idempotent re-receipt
    const receiveRes2 = await SmartStock.receivePO(validPO.id);
    assert.strictEqual(receiveRes2.replayed, true, 'Subsequent receive must be replayed without double addition');

    const afterSecond = (await SmartStock.getProducts()).find(p => p.id === prod.id);
    assert.strictEqual(afterSecond.stock_on_hand, 30, 'Stock must not increase on replayed receipt');
});

test('17. Explicitly empty catalog does not resurrect backend products', async () => {
    setupTestUser('emptycatalog@sharmakirana.in');
    
    // Explicitly set catalog to empty array
    const key = SmartStock.getUserKey('smartstock_local_products');
    global.localStorage.setItem(key, JSON.stringify([]));

    // Mock fetch to simulate backend responding with default items
    const origFetch = global.fetch;
    let backendCalled = false;
    global.fetch = async () => {
        backendCalled = true;
        return {
            ok: true,
            json: async () => [{ id: 'backend-ghost', name: 'Ghost Item' }]
        };
    };

    try {
        const products = await SmartStock.getProducts();
        assert.strictEqual(products.length, 0, 'Explicitly empty catalog must remain empty');
        assert.strictEqual(backendCalled, false, 'Backend must not be queried when local catalog key is explicitly present');
    } finally {
        global.fetch = origFetch;
    }
});

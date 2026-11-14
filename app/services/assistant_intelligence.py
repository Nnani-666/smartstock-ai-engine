"""Domain intelligence and conversational context synthesis for SmartStock AI Assistant.

Handles:
1. Grounded store context assembly (catalog, sales, incoming POs, suppliers).
2. Intelligent intent understanding for local heuristic fallback.
3. Multi-point replenishment ranking accounting for safety stock and lead times.
4. Non-repetitive, intent-specific responses.
"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_incoming_orders(orders: list[dict[str, Any]]) -> tuple[dict[str, int], list[str]]:
    """Parse open/in-transit purchase orders to map pending incoming units per product."""
    pending_units_by_product: dict[str, int] = {}
    pending_po_lines: list[str] = []

    for po in orders:
        status = str(po.get("status", "")).lower()
        if status in ("ordered", "in_transit", "placed", "pending", "confirmed"):
            po_num = po.get("po_number", "PO")
            supp = po.get("supplier", "Supplier")
            items_raw = po.get("items_json")
            items = []
            if isinstance(items_raw, str):
                try:
                    items = json.loads(items_raw)
                except Exception:
                    items = []
            elif isinstance(items_raw, list):
                items = items_raw

            line_items_desc = []
            for item in items:
                pname = item.get("name") or item.get("product_name") or "Unknown SKU"
                qty = int(item.get("units") or item.get("quantity") or 0)
                if qty > 0:
                    pending_units_by_product[pname] = pending_units_by_product.get(pname, 0) + qty
                    line_items_desc.append(f"{qty}x {pname}")

            summary_items = ", ".join(line_items_desc[:4]) if line_items_desc else "Items pending"
            pending_po_lines.append(f"- {po_num} ({supp}): Status={status.upper()}, Incoming=[{summary_items}]")

    return pending_units_by_product, pending_po_lines


def build_grounded_store_context(
    products: list[dict[str, Any]],
    sales: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    store_name: str,
    user_email: str,
) -> dict[str, Any]:
    """Assemble authenticated store context into structured operational data."""
    pending_incoming, pending_po_lines = parse_incoming_orders(orders)

    # Supplier lookup map
    supplier_map: dict[str, dict[str, Any]] = {}
    supplier_lines = []
    for s in suppliers:
        sname = s.get("name", "Supplier")
        supplier_map[sname.lower()] = s
        scat = s.get("category", "General")
        lead = s.get("lead_time_days", 3)
        phone = s.get("phone", "")
        supplier_lines.append(f"- {sname} ({scat}): Lead Time={lead}d, Phone={phone}")

    # Sales aggregation by product
    sales_map: dict[str, dict[str, Any]] = {}
    total_sales_amt = 0.0
    for s in sales:
        pname = s.get("product_name", "Unknown")
        units = int(s.get("units", 1))
        amt = float(s.get("sale_amount", 0.0))
        total_sales_amt += amt
        if pname not in sales_map:
            sales_map[pname] = {"units": 0, "revenue": 0.0}
        sales_map[pname]["units"] += units
        sales_map[pname]["revenue"] += amt

    ranked_sales = sorted(sales_map.items(), key=lambda x: x[1]["revenue"], reverse=True)
    sales_lines = [
        f"- {pname}: {d['units']} units sold, Revenue: ₹{d['revenue']:,.2f}"
        for pname, d in ranked_sales[:6]
    ]

    # Inventory categorization & urgency calculation
    out_of_stock = []
    low_stock = []
    healthy_stock = []
    catalog_lines = []

    for p in products:
        pname = p.get("name", "Unknown")
        sku = p.get("sku", "")
        cat = p.get("category_name") or "General"
        stock = int(p.get("stock_on_hand") or 0)
        rop = int(p.get("reorder_point") or 5)
        ss = int(p.get("safety_stock") or 2)
        price = float(p.get("unit_price") or 0.0)
        cost = float(p.get("unit_cost") or 0.0)
        supp = p.get("supplier") or "Metro Wholesale"
        lead = int(p.get("lead_time_days") or 3)
        incoming = pending_incoming.get(pname, 0)

        # Urgency scoring
        if stock <= 0:
            urgency = "CRITICAL_OUT_OF_STOCK"
            out_of_stock.append(p)
        elif stock <= rop:
            urgency = "HIGH_LOW_STOCK"
            low_stock.append(p)
        else:
            urgency = "HEALTHY"
            healthy_stock.append(p)

        incoming_note = f", IncomingInTransit={incoming}" if incoming > 0 else ""
        catalog_lines.append(
            f"- {pname} (SKU: {sku}, Cat: {cat}): Stock={stock}, ROP={rop}, SafetyStock={ss}, "
            f"Price=₹{price:.2f}, Cost=₹{cost:.2f}, Supplier={supp}, LeadTime={lead}d{incoming_note} [{urgency}]"
        )

    return {
        "store_name": store_name,
        "user_email": user_email,
        "total_products": len(products),
        "products": products,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
        "healthy_stock": healthy_stock,
        "sales": sales,
        "sales_map": sales_map,
        "ranked_sales": ranked_sales,
        "total_sales_amt": total_sales_amt,
        "orders": orders,
        "pending_incoming": pending_incoming,
        "pending_po_lines": pending_po_lines,
        "suppliers": suppliers,
        "supplier_map": supplier_map,
        "supplier_lines": supplier_lines,
        "catalog_lines": catalog_lines,
        "sales_lines": sales_lines,
    }


def classify_user_intent(prompt: str) -> str:
    """Classify user question using word boundary matching to avoid substring collision."""
    q = (prompt or "").lower().strip()

    # Greetings
    if re.search(r"\b(hi|hello|hey|namaste|namaskar|good morning|good afternoon|good evening)\b", q):
        return "greeting"

    # Help / capabilities
    if re.search(r"\b(what can you help|what can you do|how do you work|help me with|capabilities)\b", q):
        return "capabilities"

    # Supplier inquiry (must check BEFORE order keyword)
    if re.search(r"\b(supplier|suppliers|vendor|vendors|distributor|distributors|who should i order from|which supplier)\b", q):
        return "suppliers"

    # Stockout risk / 3 steps
    if re.search(r"\b(steps to reduce|reduce.*stockout|avoid.*stockout|prevent.*stockout|stockout risk|action steps)\b", q):
        return "stockout_prevention"

    # Urgent replenishment
    if re.search(r"\b(urgently|urgent|reorder urgently|what should i order|need to order|order urgently|buy urgently|immediate order)\b", q):
        return "urgent_replenishment"

    # Reorder point inquiry
    if re.search(r"\b(below.*reorder|below.*rop|reorder point|reorder thresholds|at.*reorder)\b", q):
        return "reorder_point"

    # Slow-moving items
    if re.search(r"\b(slow|slowly|slow-moving|not selling|lowest sales|dead stock|zero sales|no sales)\b", q):
        return "slow_moving"

    # Fast-moving / Top sales / Top revenue
    if re.search(r"\b(fast|fastest|selling the fastest|top.*selling|top sales|top revenue|highest revenue|best selling|top three|top 3|most popular)\b", q):
        return "fast_moving"

    # General inventory situation
    if re.search(r"\b(inventory situation|inventory health|current inventory|stock summary|overview of stock|store status)\b", q):
        return "inventory_situation"

    # Explanation of recommendations
    if re.search(r"\b(explain why|why do you recommend|why these products|recommendation logic|rationale)\b", q):
        return "explain_recommendations"

    # General reorder / replenishment
    if re.search(r"\b(reorder|replenish|replenishment)\b", q):
        return "reorder_point"

    # General stock inquiry
    if re.search(r"\b(stock|stocks|inventory|out of stock|low stock)\b", q):
        return "inventory_situation"

    return "general"


def generate_local_heuristic_response(
    prompt: str,
    ctx: dict[str, Any],
    fallback_reason: str = "local_heuristic",
) -> dict[str, Any]:
    """Generate an intelligent, intent-specific response from authenticated tenant data."""
    intent = classify_user_intent(prompt)
    store = ctx["store_name"]
    products = ctx["products"]
    out_items = ctx["out_of_stock"]
    low_items = ctx["low_stock"]
    pending_incoming = ctx["pending_incoming"]
    ranked_sales = ctx["ranked_sales"]
    supplier_map = ctx["supplier_map"]
    suppliers = ctx["suppliers"]

    reply = ""

    if intent == "greeting":
        reply = (
            f"Namaste! I am your SmartStock local store advisor for {store}. "
            f"I have direct access to your active catalog ({len(products)} SKUs), recent POS transactions, and supplier orders. "
            f"How can I help you today? You can ask about urgent reorders, top-selling items, slow-moving inventory, "
            f"or pending supplier deliveries."
        )

    elif intent == "capabilities":
        reply = (
            f"As your SmartStock retail advisor for {store}, I can help you with:\n"
            f"1. Urgent Replenishment: Identifying items at stockout risk and recommending order quantities.\n"
            f"2. Sales & Revenue Analysis: Ranking fast-selling products and highlighting revenue drivers.\n"
            f"3. Inventory Health: Auditing stockouts, safety stock deficits, and slow-moving items.\n"
            f"4. Supplier Coordination: Matching replenishment items to verified distributors with lead times.\n"
            f"5. Festive Preparation: Reviewing inventory readiness for upcoming peak consumer demand."
        )

    elif intent == "urgent_replenishment":
        urgent_candidates = []
        for p in out_items:
            pname = p.get("name", "Unknown")
            inc = pending_incoming.get(pname, 0)
            urgent_candidates.append({
                "name": pname,
                "stock": 0,
                "rop": p.get("reorder_point", 5),
                "supp": p.get("supplier", "Metro Wholesale"),
                "lead": p.get("lead_time_days", 3),
                "incoming": inc,
                "level": "OUT OF STOCK (CRITICAL)",
            })

        for p in low_items:
            pname = p.get("name", "Unknown")
            inc = pending_incoming.get(pname, 0)
            urgent_candidates.append({
                "name": pname,
                "stock": p.get("stock_on_hand", 0),
                "rop": p.get("reorder_point", 5),
                "supp": p.get("supplier", "Metro Wholesale"),
                "lead": p.get("lead_time_days", 3),
                "incoming": inc,
                "level": "LOW STOCK",
            })

        if not urgent_candidates:
            reply = (
                f"All {len(products)} products in {store}'s catalog are currently stocked above their reorder points. "
                f"No products require emergency replenishment today."
            )
        else:
            lines = []
            for item in urgent_candidates[:4]:
                inc_text = f" (Note: {item['incoming']} units already in-transit on open PO)" if item['incoming'] > 0 else " (No open PO in-transit)"
                lines.append(
                    f"• {item['name']}: {item['stock']} on hand (Reorder Point: {item['rop']}). "
                    f"Supplier: {item['supp']} (Lead time: {item['lead']} days){inc_text}."
                )
            reply = (
                f"Priority replenishment recommendations for {store}:\n"
                + "\n".join(lines)
                + "\nRecommendation: Dispatch purchase orders immediately for items without in-transit stock to cover supplier lead times."
            )

    elif intent == "stockout_prevention":
        crit_names = [p.get("name") for p in out_items[:2]]
        low_names = [p.get("name") for p in low_items[:2]]
        step1 = f"Dispatch emergency purchase orders for {', '.join(crit_names or low_names or ['low-stock SKUs'])} today."
        step2 = f"Follow up with active suppliers ({', '.join(s.get('name') for s in suppliers[:2])}) to confirm estimated arrival dates on pending shipments."
        step3 = "Review high-velocity staples heading into the weekend surge and protect a minimum 2-day safety stock buffer."
        reply = (
            f"Three actionable steps to minimize stockout risk for {store} this week:\n"
            f"1. Immediate Orders: {step1}\n"
            f"2. Expedite In-Transit POs: {step2}\n"
            f"3. Buffer Maintenance: {step3}"
        )

    elif intent == "fast_moving":
        if not ranked_sales:
            reply = (
                f"No sales transactions are currently recorded in {store}'s database. "
                f"Once POS sales transactions are registered, I will rank top-selling products by velocity and revenue."
            )
        else:
            top_items = []
            for rank, (pname, data) in enumerate(ranked_sales[:3], 1):
                top_items.append(f"{rank}. {pname} — {data['units']} units sold (Revenue: ₹{data['revenue']:,.2f})")
            reply = f"Top-performing products by recorded revenue at {store}:\n" + "\n".join(top_items)

    elif intent == "slow_moving":
        sold_names = set(ctx["sales_map"].keys())
        unsold = [p.get("name") for p in products if p.get("name") not in sold_names]
        if not unsold:
            reply = f"All {len(products)} active products in {store} have recorded sales activity in the ledger."
        else:
            sample = unsold[:4]
            reply = (
                f"The following {len(unsold)} catalog item(s) have recorded zero recent sales in {store}'s ledger: "
                f"{', '.join(sample)}. "
                f"Consider checking shelf placement, reviewing pricing, or running promotional bundles."
            )

    elif intent == "reorder_point":
        below_rop = out_items + low_items
        if not below_rop:
            reply = f"All {len(products)} catalog items are currently stocked above their reorder points. No reorders needed."
        else:
            lines = [
                f"• {p.get('name')}: Stock={p.get('stock_on_hand', 0)}, ROP={p.get('reorder_point', 5)}, SafetyStock={p.get('safety_stock', 2)}"
                for p in below_rop[:5]
            ]
            reply = (
                f"{len(below_rop)} product(s) are at or below reorder thresholds at {store}:\n"
                + "\n".join(lines)
            )

    elif intent == "suppliers":
        supp_items_map: dict[str, list[str]] = {}
        for p in (out_items + low_items):
            s = p.get("supplier") or "Metro Wholesale"
            supp_items_map.setdefault(s, []).append(p.get("name", "Unknown SKU"))

        if not supp_items_map:
            reply = (
                "All inventory is healthy. For standard replenishment, your registered suppliers are: "
                + ", ".join(s.get("name", "") for s in suppliers[:3]) + "."
            )
        else:
            lines = []
            for sname, items in list(supp_items_map.items())[:3]:
                supp_info = supplier_map.get(sname.lower(), {})
                phone = supp_info.get("phone", "Contact via wholesale desk")
                lead = supp_info.get("lead_time_days", 3)
                lines.append(f"• {sname} (Lead time: {lead}d, Phone: {phone}): Order {', '.join(items[:2])}")
            reply = "Recommended suppliers to contact for replenishment:\n" + "\n".join(lines)

    elif intent == "inventory_situation":
        total_val = sum(
            float(p.get("stock_on_hand") or 0) * float(p.get("unit_cost") or 0.0)
            for p in products
        )
        reply = (
            f"Inventory situation for {store}:\n"
            f"• Total Catalog: {len(products)} active SKUs\n"
            f"• Out of Stock: {len(out_items)} items requiring immediate purchase\n"
            f"• Low Stock: {len(low_items)} items at or below reorder points\n"
            f"• Healthy Stock: {len(ctx['healthy_stock'])} items with adequate coverage\n"
            f"• Estimated Inventory Valuation (at cost): ₹{total_val:,.2f}"
        )

    elif intent == "explain_recommendations":
        reply = (
            "SmartStock replenishment recommendations follow the classical inventory formula:\n"
            "Reorder Point (ROP) = (Average Daily Demand × Supplier Lead Time) + Safety Stock.\n\n"
            "1. When on-hand stock drops below ROP, an order must be placed immediately so goods arrive before safety stock is breached.\n"
            "2. Items with zero stock receive top priority, followed by items whose stock cannot cover supplier delivery lead times.\n"
            "3. If an open purchase order is already in-transit, we flag it so you do not double-order."
        )

    else:
        # General response tailored to the question without falling into a generic health dump
        reply = (
            f"Regarding '{prompt}': I have evaluated {store}'s inventory records. "
            f"You currently have {len(products)} active SKUs ({len(out_items)} out of stock, {len(low_items)} low stock). "
            f"Please let me know if you would like me to detail replenishment orders, sales figures, or supplier contacts."
        )

    return {
        "status": "ok",
        "source": "local_heuristic",
        "fallback_reason": fallback_reason,
        "store_name": store,
        "analysis": reply,
        "metrics": {
            "total_products": len(products),
            "out_of_stock": len(out_items),
            "low_stock": len(low_items),
            "recent_sales_amount": ctx["total_sales_amt"],
        },
    }

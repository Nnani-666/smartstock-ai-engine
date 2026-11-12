# SmartStock — Phase 2 Design Specification (`PHASE2_DESIGN_SPEC.md`)
**Design Direction:** **Option 2 — Premium Editorial**  
**Theme Coverage:** Full Light Mode (Warm Parchment & Pine Ink) & Dark Mode (Deep Forest Obsidian & Ivory Sage)  
**Dual-Level Intelligence:** Business Intelligence View (Shopkeeper Default) vs Technical / Academic Intelligence View (CSE Evaluation)

---

## 1. Visual Identity & Design Tokens

### Typography System
- **Editorial Display (`--font-serif`):** `'Newsreader', Georgia, serif` — Used intentionally for primary screen headlines, high-impact hero revenue metrics, and executive callouts to evoke journalistic authority and trustworthy retail ledger craft.
- **UI Body & Controls (`--font-sans`):** `'Hanken Grotesk', -apple-system, BlinkMacSystemFont, sans-serif` — Clean, legible humanist grotesk for navigation, product names, form inputs, and plain-English advice.
- **Tabular Financial & Telemetry Figures (`--font-mono`):** `'JetBrains Mono', monospace` with `font-variant-numeric: tabular-nums` — Ensures exact decimal/paise alignment (`₹1,24,500.00`), SKUs, dates, Z-scores, and RMSE metrics.

### Surface & Color Palette

| Token Role | Light Mode (`data-theme="light"`) | Dark Mode (`data-theme="dark"`) | Usage |
|---|---|---|---|
| `--bg-canvas` | `#FAF8F5` (Warm Alabaster Paper) | `#0E1412` (Deep Pine Obsidian) | Page canvas background |
| `--bg-surface` | `#FFFFFF` (Crisp Editorial Sheet) | `#151D1A` (Elevated Slate Pine) | Primary cards, ledger sheets, drawers |
| `--bg-subtle` | `#F2EFE9` (Muted Warm Stone) | `#1C2622` (Recessed Slate Well) | Wells, table headers, segmented controls |
| `--text-primary` | `#161D1A` (Charcoal Forest Ink) | `#EDF1EE` (Crisp Ivory Bone) | Headlines, primary metrics, copy |
| `--text-secondary` | `#525C57` (Slate Sage) | `#A3B0AA` (Muted Silver Sage) | Labels, timestamps, axis text |
| `--accent-primary` | `#0F382B` (Deep Editorial Pine) | `#7CC4AA` (Luminous Mineral Sage) | Primary CTAs, active nav, trend lines |
| `--accent-secondary` | `#A84A28` (Terracotta Rust) | `#E59573` (Warm Terracotta Coral) | Alerts, forecasts, low stock, urgency badges |
| `--border-hairline` | `rgba(22, 29, 26, 0.11)` | `rgba(237, 241, 238, 0.12)` | Hairline editorial rules (1px crisp lines) |
| `--status-danger` | `#B3261E` | `#F28B82` | Out of stock, oversell errors, critical Z-score |

### Anti-Clutter Editorial Guardrails
- No excessive gradients, glowing neon AI halos, 3D gimmickry, or bloated padding.
- Borders rely on crisp `1px solid var(--border-hairline)` editorial separators rather than heavy drop shadows.
- Border radii remain disciplined (`6px` inputs/buttons, `10px` structural sheets, `999px` status badges only).
- Respects `@media (prefers-reduced-motion: reduce)`.

---

## 2. Global Navigation & Layout Shell (`editorial-shell.js`)

- **Desktop & Tablet (`>= 1024px`):** Fixed crisp `248px` left rail sidebar with collapsible AI Intelligence submenu + `60px` top utility masthead featuring:
  - Screen Title & Breadcrumb
  - **Two-Level Intelligence Switch:** Segmented pill (`Business View` | `Academic View`) persisted globally
  - **Theme Switcher:** Light (`light_mode`) / Dark (`dark_mode`) toggle persisted across all screens
  - Store Pill Switcher, Notification Bell (`badge`), and Merchant Initial Avatar
- **Mobile (`< 1024px`):** Slide-over editorial drawer (`#side-drawer`) preserving legacy selectors + sticky compact top bar + accessible bottom quick-bar for Dashboard / Inventory / POS / AI.

---

## 3. Individually Designed Screen Specifications (12 Distinct Compositions)

Each screen has a bespoke structural hierarchy tailored specifically to its workflow:

1. **`01_signin.html` — Architectural Split Auth Portal:**
   - Desktop asymmetric split: Left pine editorial manifesto column (real system capabilities summary, security trust markers); Right paper auth sheet with `#tab-btn-signin` / `#tab-btn-signup`, store details, demo helper button.
   - Mobile: Single focused paper sheet with compact pine masthead.

2. **`02_overview.html` — Editorial Morning Briefing:**
   - **Asymmetric Masthead Strip:** Oversized `Newsreader` Today's Revenue hero number + date range selector (`Today`, `7 Days`, `30 Days`, `Month`, `All Time`) on the left, paired with a compact 3-column financial ledger bar (Inventory Cost Valuation, Active Items, Low/Out Alerts) separated by hairline rules.
   - **Two-Column Broadsheet Grid:**
     - *Left (60%):* "Needs Immediate Attention" actionable digest (Stockout Risks, Pending PO Deliveries, Slow-Moving Capital, Unusual Demand flags) + Quick Assistant summary callout.
     - *Right (40%):* Chronological "Floor Activity Ledger" (POS receipts + Stock inwarding + Alerts) + Weekly Demand Velocity bar sparkline.

3. **`03_inventory.html` — High-Density Retail Catalog Workbench:**
   - Sticky filter & search ribbon (Live Search, Category Dropdown, Status Pills with live counts, Sort Cycle, CSV Import/Export, `+ Add Product`).
   - Contextual **Bulk Action Bar** slides in when rows are selected (`+5 Stock`, `Export`, `Delete`).
   - Responsive Hybrid Data View: Clean hairline desktop ledger table (`SKU`, `Product`, `Category`, `Price / Cost`, `On Hand`, `Reorder At`, `Status Badge`, Inline `-1 Sell` / `+10 Stock`, `Edit`, `Delete`) + mobile stacked rows, plus a **Slide-Over Product Detail Inspector** showing supplier lead time, valuation, and margin without cluttering rows.

4. **`07_sales.html` — Dedicated Speed POS Terminal & Register:**
   - **Two-Pane Transaction Desk:**
     - *Left (55%):* Fast SKU lookup + tactile product tiles showing live available stock + single-tap add to cart & custom quantity steppers + custom transaction date toggle + idempotency-guarded "Confirm Sale" checkout bar (paise-exact math & overselling lock).
     - *Right (45%):* Live Paper Receipt Preview + Today's Shift Revenue / Margin Totals + Switchable Full Unlimited Sales History Ledger (`GET /api/v1/user/sales`) with CSV receipt summary.

5. **`05_purchase_orders.html` — Procurement & Receiving Desk:**
   - Status Filter Tabs (`All`, `AI Drafts`, `Ordered`, `In Transit`, `Completed`) + `+ New PO` button.
   - **AI Draft Composition Sheet** with top terracotta accent bar converting unreplenished low-stock items to active POs in 1 click.
   - Split Master-Detail / Expandable Order Cards showing supplier, PO date, line-item stock status badges, status advancement (`Mark In Transit`, `Cancel`), and idempotent **"Receive Stock"** confirmation modal.

6. **`05_replenishment.html` — Urgency-Triage Reorder Decision Workspace:**
   - Priority Swimlanes organized strictly by rule output:
     - **Critical / Expedite (`R1_EXPEDITE`)**
     - **Reorder Now (`R2_REORDER`)**
     - **Healthy / Hold Stock (`R3_HOLD`)**
   - *Business View:* Plain-language cards ("May run out before delivery arrives — order +20 units").
   - *Technical View:* Exposes $LTD$, Safety Stock ($Z \cdot \sigma_d \cdot \sqrt{L}$), $ROP$, $IP$, Days of Cover, and exact rule triggers.
   - Persistent bottom Draft PO Composer bar recalculating total order cost live.

7. **`04_forecasts.html` — Chart-Led Time-Series Workbench:**
   - Top SKU Switcher bar (supports BOTH Merchant Catalog items AND Kaggle 500-SKU Benchmark Explorer via Store `1–10` / Item `1–50` selector!).
   - Horizon Selector (`7d`, `14d`, `21d`, `28d`) + Granularity Toggle (`Daily` / `Weekly`) + Model Selector (`Best / Auto`, `Holt-Winters`, `Random Forest`).
   - Full-width Editorial SVG Dual-Line Chart (Actual History solid pine vs Predicted dotted terracotta + Confidence Range Shading).
   - *Business View:* Plain-English demand trend summary & upcoming stock recommendation.
   - *Technical View:* Live RMSE/MAE model benchmark table (`Naive`, `Seasonal Naive`, `Holt-Winters`, `Random Forest`) and feature engineering disclosure (`Lag 1, 7, 14, 28` + `Rolling 7d/28d`).

8. **`08_anomalies.html` — Exception Monitoring & Investigation Ledger:**
   - Connects live to `GET /anomalies` and `GET /skus`.
   - Filter bar: Store/Item selector, Detection Method (`Any`, `Z-Score |Z|>3`, `IQR 1.5x`), Date Window.
   - *Business View:* Clear "Unusual Demand Spike / Drop" incident log explaining why spikes occurred and protecting stock planning.
   - *Technical View:* Visual timeline dot plot + statistical table displaying exact `sales`, computed `z_score`, `z_flag`, `iqr_flag`, and benchmark evaluation metrics (Recall `99.8%`, Precision `57.87%`, FPR `0.0073`).

9. **`09_segmentation.html` — Visual Classification Studio (ABC-XYZ & K-Means):**
   - Connects live to `GET /skus` and `GET /segments/summary`.
   - **3x3 Interactive Nine-Box Matrix Grid** (`AX`, `AY`, `BX` -> Strategic | `AZ`, `BY`, `CX` -> Core | `BZ`, `CY`, `CZ` -> Tail) — clicking any cell filters the live SKU table below!
   - *Business View:* Plain-language tier descriptions ("Best Sellers & Reliable", "Steady Movers", "Slow Moving / Review").
   - *Technical View:* Interactive **2D K-Means Cluster Scatter SVG** (`Mean Daily Sales` vs `CV`, $K=2$, Silhouette Score `0.5847`) + ABC/XYZ distribution breakdown + guarded re-cluster confirmation modal.

10. **`10_assistant.html` — Dedicated Conversational Store Advisor:**
    - Full-height two-column workspace: Conversation Context Sidebar (live merchant catalog health snapshot scoped strictly to signed-in merchant) + Clean Conversational Message Feed (`escapeHtml` sanitized) + Quick Suggestion Chips + Prompt Input Bar (`maxlength=1000`).
    - Clearly labels response provenance (`Gemini 2.5 Flash` vs `Local Heuristic Fallback`), respects rate limiting (`429`), and never fabricates telemetry.

11. **`11_analytics.html` — Editorial Data Intelligence & Simulation Lab:**
    - **Zone A — Measured Live Store Performance:** Net Revenue, COGS, Realized Gross Profit, Gross Margin %, Top Revenue SKUs horizontal bar chart (strictly labeled **Measured Store Data**).
    - **Zone B — Benchmark Model & Policy Simulation Lab:** Static vs SmartStock Dynamic $(s, S)$ Inventory Policy comparison (`1,351` vs `621` stockout days = **54.03% Reduction**, Fill rate `98.08% -> 99.18%`) + Daily/Weekly Model RMSE/MAE Scorecard (strictly labeled **Simulated Benchmark — 500 SKUs**).

12. **`12_suppliers.html` — Procurement Partners Directory:**
    - Editorial vendor dossier cards with lead-time tags, hub location, phone (`tel:`), supplied catalog pills, historical PO spend ledger, `+ Add Supplier` modal, and 1-tap `Create PO` shortcut.

13. **`06_settings.html` — Account, Preferences & System Calibration:**
    - Clean left-indexed preference groups: Store Profile (`edit`), Appearance (`Light` / `Dark` theme switch), Intelligence Default (`Business` vs `Technical`), Stock Alert Threshold stepper, Demo Catalog Utilities, and Session Sign Out.

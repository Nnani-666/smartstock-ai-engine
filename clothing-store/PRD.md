# PRD: "OKTA/9" Full-Stack 360° Fashion E-Commerce Platform

## 1. System Vision & Architecture
OKTA/9 is a production-grade luxury fashion e-commerce platform combining:
- **Frontend**: Single-page high-craft UI with real 360° interactive turntable physics, multi-product wardrobe switching, notched ticket card design system, sliding size selectors, animated accordions, dynamic hotspot inspection, and flying-card cart animations.
- **Backend (Python / FastAPI)**: Asynchronous REST API with strict Pydantic v2 schemas, database persistence, inventory control, and enterprise-grade security middleware.
- **Database Layer**: SQLite default persistence with plug-and-play support for external PostgreSQL / Supabase databases via connection string in `.env`.
- **Security Suite**:
  - Security headers (HSTS, X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy).
  - Rate limiting on API routes.
  - Strict input sanitization and payload size limits.
  - Atomic stock deductions and concurrency-safe transactions.
  - Zero SQL injection via parameterized SQLite/Postgres drivers.

## 2. Multi-Garment Product Catalog
1. **The Contour Lines Metallic Puffer** (€ 1.120) — Liquid-silver ripstop with topographic contour print, stand collar, two-way zip.
2. **The Archive Varsity Bomber** (€ 890) — Melton wool body, Italian lambskin sleeves, chenille gothic embroidery.
3. **The Tactical Storm Trench** (€ 940) — Water-resistant 3-layer bonded nylon, modular storm flap, magnetic FIDLOCK closures.
4. **The Winged Skull Heavy Tee** (€ 180) — 320 GSM combed Portuguese cotton, vintage washed black, distressed raw hem.
5. **The Archival Boxy Zip Hoodie** (€ 420) — 500 GSM loopback French terry, custom heavy silver two-way hardware.
6. **The Pleated Cargo Pant** (€ 360) — Italian wool-blend twill, wide leg silhouette, articulated utility cargo pockets.

## 3. Endpoints Specification
- `GET /api/health` — System status, database health, security audit info.
- `GET /api/products` — Catalog listing with category filter, sorting, and availability.
- `GET /api/products/{id}` — Full product details, hotspots, sizing, and inventory.
- `POST /api/cart/validate` — Server-side cart validation and pricing calculation.
- `POST /api/orders/checkout` — Atomic stock reservation, payment simulation, and order receipt generation.
- `GET /api/orders/{id}` — Retrieve confirmed order details.
- `POST /api/wishlist/toggle` — Save/unsave products for merchant session.
- `GET /api/search` — Query products by title, category, material.

# PRD: Critical Cross-Account AI Data Isolation

## Problem Statement
When a user logs out of Account A and logs into Account B in the SmartStock web application, queries to the Smart Assistant may return sales/inventory data belonging to Account A instead of Account B. This violates tenant isolation and presents a severe confidentiality vulnerability.

## User Personas
- **Tenant A Shopkeeper**: Needs strict confidentiality of their inventory, supplier agreements, and sales revenues.
- **Tenant B Shopkeeper**: Must never see Tenant A's products, sales transactions, or profit margins under any circumstances.

## Requirements
1. **Authoritative Backend Tenant Context**: Tenant identity is exclusively derived from validated server-side session token.
2. **Complete Query Isolation**: All database lookups (products, sales, orders, suppliers) must filter by authenticated tenant ID / email.
3. **Frontend Session Sanitization**: Logout must immediately revoke backend session, clear all cached user data in `localStorage` and `sessionStorage`, reset chat thread in `10_assistant.html`, and cancel any pending requests.
4. **Login Isolation**: Logging into a new account must load fresh context, isolated conversation thread, and isolated store statistics.
5. **Multi-Model Isolation**: Switching between Gemini 3.5 Flash-Lite, Gemini 3.1 Flash-Lite, and Local Heuristic must never leak cross-tenant context.
6. **Zero Demo Data Bleed**: If an account has 0 sales or empty inventory, it must state so honestly; never substitute demo data or another tenant's records.

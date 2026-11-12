# SmartStock — Project Definition (.planning/PROJECT.md)

## 1. Project Identity
- **Project Name:** SmartStock — Supply Chain Demand & Inventory Optimization Engine
- **Primary Repository:** `https://github.com/Nnanirepo/smartstock`
- **Current Phase:** Phase 0 — Baseline Protection, Recovery & Comprehensive System Audit
- **Operating Protocol:** Power Mode (GSD Spec-Driven Architecture + Ralph Memory Loop + CodeRabbit Security Gates)

## 2. Core Project Objectives
1. Provide small and medium retail merchants with an intuitive, mobile-first inventory decision engine that eliminates stockouts and minimizes dead inventory.
2. Deliver a academically rigorous Data Science & AI pipeline combining classical statistical models (Holt-Winters, Z-score, IQR) with Machine Learning (Random Forest, K-Means) for college evaluation.
3. Bridge the academic analytics engine with live transactional point-of-sale and purchase order workflows.
4. Provide enterprise-grade multi-tenant data isolation, security, and atomic data integrity.

## 3. Technology Stack Overview
- **Backend:** Python FastAPI, Uvicorn, Pydantic, Scikit-Learn, Statsmodels, Pandas, NumPy, SQLite, Supabase SDK.
- **Frontend:** Stitch SPA (HTML5, Tailwind CSS, Vanilla JS, Material Symbols).
- **Mobile:** iOS (SwiftUI + WKWebView) & Android (Kotlin + Jetpack Compose + WebView).
- **Quality Assurance:** Pytest (55 tests), Node test runner (17 tests), Playwright (8 E2E tests).
- **AI Assistant:** Gemini 2.5 Flash API (with heuristic offline fallback).

## 4. Key Architectural Trade-offs
- **Dual Database Strategy:** SQLite is leveraged for ultra-fast local development, reproducible ML pipelines, and offline-capable single-node instances (`data/supply_chain.db`), while Supabase PostgreSQL provides cloud synchronization and relational schema integrity.
- **Explainable Rules vs Black-Box AI:** In replenishment decisions, black-box deep learning is rejected in favor of an explainable priority rule expert system (R1/R2/R3) driven by quantitative lead-time forecasts and safety stocks. Local shopkeepers require clear rationale ("Why should I reorder?") rather than uninterpretable probabilities.
- **Hybrid Frontend Bridge:** The frontend uses an asynchronous bridge pattern (`smartstock-bridge.js`) allowing it to run smoothly against local storage, the local FastAPI server, or direct Supabase PostgreSQL connections.

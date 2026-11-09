# Trend Mix release gates — 27 October 2026

This is a development checklist, **not** an assertion of launch readiness.

## Built / available in local QA
- Python Flask storefront, responsive shop, unchanged homepage hero.
- Admin dashboard with access protection; product drafts stored locally only.
- Supplier price calculator using explicit purchase cost, shipping, packaging, payment costs, VAT rate and target margin.
- Product opportunity review with **no fabricated live search volumes, conversion rates or supplier data**.
- Support email reply drafts and human-escalation decisioning; no automatic incoming/outgoing email.
- Customer accounts in local SQLite prototype, unavailable on serverless deploy by default.
- Mock checkout; no live paid orders.

## Must remain off until integrated and verified
- Push supplier products to public catalog: supplier credentials, approved images/product information, stable SKU, inventory, shipping zone, reliable tax handling, preview, explicit publish approval, rollback, audit trail and production storage.
- Google Search/Trends / competitive analytics: licensed data providers, provenance, dates, observed metrics; show uncertainty instead of fake percentages.
- Cross-supplier niche discovery: real supplier API contracts and coverage, cost/stock/delivery/returns evidence and vendor approval.
- Real payment/order webhooks: signature validation, replay resistance, persistent state, payment reconciliation and privacy controls.
- Automatic AI replies and human escalation emails: domain/inbox setup, inbound webhook signature verification, mail provider sender validation, duplicate-event handling, outbound send gating, spam controls, human escalation destination and a complete audit trail.
- Production identity: persistent storage, verified emails, password reset, abuse prevention, retention/deletion processes.
- EU consumer-law text, business data, VAT scheme and tax review, shipping/returns arrangements.

## Laptop QA before launch
Run `python -m pytest -q`, then inspect storefront/shop filters, language switch, categories, products, cart, checkout, customer account prototype, admin pages and device widths 320/375/390/desktop. Protect admin credentials, never paste keys. Never assume successful unit tests establish complete security.

Do not merge to main, deploy, or enable sales until above launch blockers are cleared.

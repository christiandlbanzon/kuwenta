# Kuwenta — PRD

> Source of truth for the v1 spec. The implementation plan derived from this lives in [`PLAN.md`](PLAN.md).

## 1. Overview
A multi-user, PH-focused personal finance tracker that uses LLMs to:
- Auto-categorize expenses from natural language
- Answer financial questions in plain English / Taglish
- Detect spending anomalies and recurring subscriptions
- Generate monthly personalized budget coaching
- Forecast cash flow based on patterns
- Extract structured data from receipt photos (Gemini Vision)
- Parse Gmail bank/wallet notifications (GCash, Maya, BDO, BPI, UnionBank) — v2

Runs entirely on free-tier LLM APIs ($0/month operating cost). PH-specific: peso formatting, local categories (palengke, sari-sari, jeepney, Grab, Lazada, Shopee, GCash, Pag-IBIG, SSS, PhilHealth, etc.).

## 2. Goals & Non-Goals
**v1 goals:** multi-user-ready architecture (auth, data isolation), single-user UX, manual entry + bulk CSV + receipt OCR, LLM categorization + NL Q&A + monthly insights, eval suite (categorization accuracy + Q&A correctness), deployed (not localhost), $0/month ops cost.

**v1 non-goals:** sharing/multi-user UX, SMS parsing, bank API integration, mobile app, investment tracking.

**v2 stretch:** email forwarding parser, AI budget coaching (Pag-IBIG, emergency fund), family sharing, recurring detection, advanced forecasting.

## 3. Users & Use Cases
Primary user: PH-based developer (~₱140k/month) planning a Pag-IBIG-funded house build. Top stories:
- Type "180 jollibee lunch yesterday gcash" → parsed, categorized, stored
- Snap receipt → vendor, items, total, date, category extracted
- "How much did I spend on transportation last month?" → answered in PHP-formatted prose
- Monthly insight: "You spent ₱8,400 on food delivery this month, 32% above your 3-month average."
- Set monthly budget per category → real-time progress, warnings at 80%/100%

## 4. Tech Stack
Python 3.11+, FastAPI async, SQLModel + SQLite (Postgres-ready), JWT auth, Next.js 14 + Tailwind + shadcn/ui, Gemini Flash 2.0 primary / Groq Llama 3.3 70B fallback / Ollama for local dev (with `LLMProvider` abstraction), custom SQLite tracer (NOT Langfuse — decided during scoping), APScheduler for jobs, uv + ruff + mypy strict on core + pytest, deploy on Fly.io/Railway + Vercel.

## 5. Data Model
See [`backend/app/models/`](backend/app/models/) for the SQLModel implementation. Tables:
- `User` (email, hashed_password, display_name, currency=PHP, timezone=Asia/Manila)
- `Account` (type: cash/bank/ewallet/credit_card, institution, current_balance)
- `Category` (type: expense/income, parent_id, is_default — seeded with PH defaults on signup)
- `Transaction` (amount, type, description, merchant, occurred_at, source: manual/receipt_ocr/csv_import/email_parse, raw_input, ai_confidence)
- `Receipt` (image_path, extracted_data JSON, transaction_id)
- `Budget` (category_id, amount, period: monthly/weekly, is_active)
- `Insight` (type: monthly_summary/anomaly/recurring_detected, content markdown, period range)
- `LLMCall` (purpose, provider, model, tokens, latency_ms, success, error — observability + cost tracking)

PH default categories on signup: Food & Dining, Groceries (Palengke/Supermarket), Transportation (Grab/Jeepney/Gas), Bills (Meralco, Maynilad, Globe, PLDT), Shopping (Lazada, Shopee, Mall), Healthcare, Entertainment, Government Contributions (SSS, PhilHealth, Pag-IBIG, BIR), Savings, Investments, Family Support, Tithing, Others.

## 6. Core Features (v1)

### 6.1 Auth
Email + password, JWT, password reset (Resend free tier or console-log in v1). Every query scoped by `user_id`.

### 6.2 Manual Transaction Entry
Free-text quick-add → LLM parses to structured transaction. Confirmation step before save. Standard form alternative.

### 6.3 Receipt OCR
Upload photo → Gemini Vision extracts merchant, line items, subtotal, tax, total, date, payment method → auto-categorize → user confirms.

### 6.4 CSV / Bulk Import
Upload bank statement CSV. LLM categorizes in batches of 20+ to respect rate limits. Preview + override before bulk save.

### 6.5 Auto-Categorization
Every transaction gets a category prediction with confidence. Confidence < 0.7 flagged for review. User overrides feed into a few-shot examples store.

### 6.6 Natural Language Q&A
Chat-style. Backend uses **function-calling with fixed query primitives** (NOT LLM-generated SQL — see PLAN.md §Cross-cutting decisions). Tools: `sum_by_category`, `sum_by_merchant`, `transactions_filter`, `compare_periods`, `budget_status`, `top_categories`, `account_balances`. Planner LLM picks tool + args; validator whitelists; tools execute parameterized scoped queries; summarizer LLM produces PHP-formatted prose with cited transaction IDs.

### 6.7 Monthly Insights
Cron on the 1st. Pulls last month's transactions, computes stats, LLM generates markdown summary: total spent, top 3 categories, anomalies (>2σ from 3-month avg), positive trends, suggestions. Stored in `Insight`.

### 6.8 Anomaly Detection
3-month rolling avg + stddev per category. Flag totals > 2σ. LLM explains: "Your transportation spending this week is unusually high. Most of it (₱2,400) came from Grab rides on weekday evenings — different from your usual Mon-Wed pattern."

### 6.9 Budget Tracking
Monthly budgets per category. Progress bars, projected end-of-month, warnings at 80% and 100%.

### 6.10 Dashboard
Net worth (sum of account balances), this month spent/income/savings rate, spending by category (donut), recent transactions, active insights, quick-add input pinned at top.

## 7. LLM Architecture
`LLMProvider` Protocol with `complete`, `complete_with_vision`, `complete_structured`. Implementations: `GeminiProvider`, `GroqProvider`, `OllamaProvider`. Routing per purpose (categorization → Gemini, vision/OCR → Gemini, Q&A → Gemini with Groq fallback, insights → Gemini with Groq fallback, local dev → Ollama). Every call logged to `LLMCall`. Token-bucket rate limit for Gemini (15 req/min). `/admin/llm-stats` endpoint for observability.

## 8. Eval Suite (CRITICAL)
See [`backend/evals/README.md`](backend/evals/README.md). Four eval tracks: categorization (50+ labeled PH txns, F1 + confusion matrix), Q&A (30+ pairs, LLM-as-judge with two-judge agreement), OCR (10-20 receipts, fuzzy match + line-item recall), insights (synthetic datasets with known anomalies, hallucination check). Token/cost tracking. Results in markdown reports surfaced in README.

## 9. Architecture
```
┌──────────────────┐     ┌──────────────────┐
│   Next.js App    │────▶│   FastAPI BE     │
│  (Vercel free)   │     │   (Fly.io free)  │
└──────────────────┘     └────────┬─────────┘
                                  │
                ┌─────────────────┼──────────────────┐
                ▼                 ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │   SQLite     │  │ LLM Router   │  │  APScheduler │
        │ (persistent  │  │ Gemini/Groq/ │  │  (insights,  │
        │   volume)    │  │   Ollama     │  │   anomaly)   │
        └──────────────┘  └──────────────┘  └──────────────┘
```

## 10. Build Order
See [`PLAN.md`](PLAN.md) — phased, not calendar-bound.

## 11. Code Quality
Type hints everywhere; mypy strict on `app/core/`, `app/llm/`, `app/services/`, `app/tools/`. Async/await throughout. 70%+ coverage on services and LLM logic. No secrets in code; `.env` + pydantic-settings. Pre-commit: ruff + mypy + pytest. Conventional commits. Every prompt as a separate file in `app/llm/prompts/` with version comments.

## 12. Constraints
- Free tier only.
- Multi-user from day 1.
- Evals are not optional.
- PH-specific is a feature.
- Ship deployed.

# Kuwenta — Implementation Plan

This is the build plan derived from `PRD.md` plus two architectural decisions agreed during scoping:

1. **NL Q&A uses function-calling, not LLM-generated SQL.** A fixed set of typed query primitives (defined in `app/tools/finance_tools.py`) is exposed to the LLM via tool-calling. The LLM picks tools and arguments; tools execute parameterized queries against the user's scoped data and return structured results; a second LLM call summarizes them in PHP-formatted prose. This eliminates the SQL-injection / unbounded-query attack surface, makes Q&A directly evaluable (we can assert which tool got called with what args), and is defensible in interviews.

2. **Observability uses a custom SQLite tracer**, not Langfuse. Every LLM call goes through a context-managed `trace()` wrapper that writes a row to the `LLMCall` table with provider, model, tokens, latency, success, error. A `/admin/llm-stats` endpoint and a one-page dashboard read from this table. No extra service to host.

The PRD's "3 weekends" framing is treated as **logical phases, not calendar deadlines** — phases are ordered so each one ends in a working, demoable state.

---

## Phase 1 — Foundation

**Outcome:** authenticated user can log in, hit `/healthz`, and see Swagger docs. LLM provider abstraction wired with Gemini, callable from a script. SQLite schema migrated.

- Repo skeleton (this commit): monorepo layout, `pyproject.toml`, `.env.example`, `.gitignore`, ruff + mypy configs, model files with full schema from PRD §5
- `app/db.py`: SQLModel engine + async session factory (using `aiosqlite`)
- `app/config.py`: pydantic-settings for all env vars (`GEMINI_API_KEY`, `GROQ_API_KEY`, `JWT_SECRET`, `DATABASE_URL`, `LLM_PROVIDER_DEFAULT`, etc.)
- `app/core/security.py`: bcrypt password hash, JWT encode/decode helpers
- `app/core/auth.py`: signup, login, current-user dependency
- `app/core/deps.py`: `get_session()`, `get_current_user()`, `require_user_scope()` (a helper that returns a query builder pre-filtered by `user_id` — every service uses this so we cannot accidentally leak across users)
- `app/llm/base.py`: `LLMProvider` Protocol + `Message`, `CompletionResult`, `ToolCall` dataclasses
- `app/llm/providers/gemini.py`: text + vision + structured-output (using `response_schema`)
- `app/llm/tracer.py`: `async with trace(purpose=...)` context manager that wraps a call, captures latency/tokens/error, writes to `LLMCall`
- `app/llm/rate_limit.py`: in-process token bucket for Gemini (15 req/min) — async-safe
- `app/llm/router.py`: `get_provider(purpose)` returning the right provider by purpose with fallback chain
- Default category seeding on signup (`app/services/seed.py`)
- One smoke test: signup → login → call Gemini through the router → verify `LLMCall` row written

**Don't build yet:** Groq/Ollama providers (stubs only), Q&A, OCR, insights, frontend.

## Phase 2 — Core entry & dashboard

**Outcome:** user can type "180 jollibee lunch yesterday gcash" and end up with a correctly categorized transaction. Dashboard shows recent transactions and category totals.

- `app/services/transactions.py`: CRUD scoped to user
- `app/services/categorization.py`: takes free text → calls categorization LLM with few-shot examples → returns `(category_id, confidence, merchant)`. Few-shot examples loaded from a JSONL file that grows as users override categories (write-back on override).
- `app/services/parse_quickadd.py`: free-text → structured transaction (amount, account hint, date, description). Uses `complete_structured` with a Pydantic schema.
- `app/api/transactions.py`: `POST /transactions/quick-add`, `POST /transactions`, `GET /transactions`, `PATCH /transactions/{id}` (override → write-back to few-shot store), `DELETE`
- `app/api/accounts.py`, `app/api/categories.py`: CRUD
- Frontend: Next.js scaffold (`create-next-app`), shadcn install, login/signup pages, dashboard page with quick-add input + transaction list + category donut, JWT in httpOnly cookie set via Next.js route handler proxying to FastAPI
- Tests: `test_categorization.py`, `test_quickadd_parse.py` (mocked LLM), `test_transactions_scope.py` (asserts user A cannot read user B's transactions)

## Phase 3 — Power features

**Outcome:** the app does real work end-to-end.

- **Receipt OCR** (`app/services/ocr.py`): upload endpoint accepts image, stores under `data/receipts/<user_id>/<uuid>.<ext>`, calls Gemini Vision with the receipt prompt, returns extracted draft transaction for user confirmation. Receipt row links to transaction once confirmed.
- **CSV import** (`app/services/csv_import.py`): accepts CSV, validates against expected schema, batches rows in groups of 20 for categorization (single LLM call per batch with structured output schema), preview screen, bulk save.
- **NL Q&A** (`app/services/qa.py` + `app/tools/finance_tools.py`):
  - Tools: `sum_by_category(period, category?)`, `sum_by_merchant(period)`, `transactions_filter(min_amount?, max_amount?, period, category?, merchant_substring?)`, `compare_periods(category, period_a, period_b)`, `budget_status(category, period)`, `top_categories(period, n)`, `account_balances()`
  - Each tool is a typed Python function with a Pydantic args schema; tool registry exposes JSON schema to the LLM
  - QA flow: user query → planner LLM picks tool(s) → validator (whitelist tool name + Pydantic-validate args) → execute scoped to `current_user.id` → results dict → summarizer LLM produces prose answer with cited transaction IDs
  - Input is never interpolated into queries; all WHERE clauses use parameterized SQLModel filters
- **Budgets** (`app/api/budgets.py`, `app/services/budgets.py`): CRUD + progress endpoint that returns `{spent, budgeted, projected_eom, percent}` per active budget
- Frontend: receipt upload page, CSV import wizard, Q&A chat page, budgets page with progress bars, charts (Recharts)

## Phase 4 — Evals, insights, anomaly

**Outcome:** monthly insights generate automatically; anomalies show up on the dashboard; eval suite runs in CI and surfaces results in `evals/results/`.

- **Eval suite** (`evals/`):
  - `eval_categorization.py`: 50+ hand-labeled PH transactions, computes accuracy + per-category F1 + confusion matrix, writes markdown report
  - `eval_qa.py`: 30+ Q/A pairs against a fixed 500-transaction fixture; LLM-as-judge with rubric; two-judge agreement check
  - `eval_ocr.py`: 10–20 receipt images with ground truth; merchant fuzzy match, total within ₱1, category match, line-item recall
  - `eval_insights.py`: synthetic datasets with known anomalies; judge checks if insight identifies the right anomaly and grounds claims in actual data (hallucination check)
  - `evals/conftest.py` skips evals by default (pytest marker `eval`); CI runs them on a separate workflow with API keys
- **Monthly insights** (`app/jobs/tasks.py` + APScheduler): runs on the 1st of each month (and on-demand endpoint), generates markdown summary, stores in `Insight` table
- **Anomaly detection** (`app/services/anomaly.py`): per-category 3-month rolling mean + stddev computed in SQL; flag transactions or category totals > 2σ; LLM generates explanation only for flagged items
- **Cost tracking endpoint** (`app/api/admin.py`): `/admin/llm-stats` returns daily request counts, p50/p95 latency, error rate per provider, projected cost if paid

## Phase 5 — Deploy + README

- Backend on Fly.io with persistent volume mounted at `/data` (SQLite + receipts)
- Frontend on Vercel; `NEXT_PUBLIC_API_URL` pointing to fly.dev URL
- Dockerfile, fly.toml, GitHub Actions CI (ruff + mypy + pytest + eval suite on cron)
- README per PRD §12: hero screenshot, demo video link, architecture diagram, AI features with screenshots, eval results, cost analysis, what-I-learned, run-locally, roadmap

---

## Cross-cutting decisions

- **Money:** `Decimal` everywhere in Python; stored as `NUMERIC` in SQLite via `Column(Numeric(14, 2))`. Never `float`.
- **Timezone:** all timestamps stored UTC; user-facing display uses `Asia/Manila`. `occurred_at` is a `datetime` with tz-aware UTC value.
- **Migrations:** Alembic from day 1 — even though `create_all` would work, Alembic is interview-credibility cheap to set up and avoids a painful retrofit when deploying.
- **Multi-user safety net:** every service function takes `user_id: UUID` as the first arg. A pytest fixture creates two users and asserts cross-user reads return empty for every list endpoint. This catches the most likely shipping-bug.
- **Prompts:** every prompt in `app/llm/prompts/*.txt` (or `.md`) with a header comment `# version: N` and a changelog block at the top of the file. The categorization prompt's few-shot examples are loaded from `data/few_shot/categorization.jsonl` so they can grow without changing code.
- **Rate limit handling:** Gemini token bucket; on rate-limit error, retry with exponential backoff up to 3x; on persistent failure, fall back to Groq for QA/insights and surface error for OCR (vision fallback is harder).
- **Frontend auth:** JWT issued by FastAPI; Next.js route handler stores it in an httpOnly, SameSite=Lax, Secure cookie. Frontend never sees the token. This is more secure than localStorage and a common interview talking point.

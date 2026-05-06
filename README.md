# Kuwenta

PH-focused, AI-powered personal finance tracker. Auto-categorizes expenses, answers questions in plain English, OCRs receipts, and generates monthly insights — all on free-tier LLM APIs ($0/month operating cost).

> **Status:** in active development. See [`PLAN.md`](PLAN.md) for the build plan and [`PRD.md`](PRD.md) for the spec.

## Stack
- **Backend:** Python 3.11+, FastAPI (async), SQLModel + SQLite, Alembic, APScheduler
- **Frontend:** Next.js 14 (App Router), Tailwind, shadcn/ui
- **LLM:** Gemini Flash 2.0 primary, Groq Llama 3.3 70B fallback, Ollama for local dev
- **Tooling:** uv, ruff, mypy strict on core, pytest

## Run locally

### Backend (works today)

```bash
cd backend
uv sync
cp ../.env.example ../.env       # fill in JWT_SECRET; GEMINI_API_KEY needed for LLM-backed routes

# First run only — generate the initial migration from the SQLModel schema:
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head

# Run the dev server:
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs

# Tests (no API key required — LLMs are mocked):
uv run pytest
```

### Frontend (Phase 2 polish — not yet scaffolded)

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --eslint --src-dir --import-alias "@/*"
npx shadcn@latest init
npm run dev
```

## Status

Phases 1–4 backend done — full v1 backend is functional, tested, and deploy-ready.

**Auth & data:**
- ✅ Auth (signup/login/me) with JWT, OAuth2 form variant for Swagger
- ✅ Multi-user data isolation, enforced by HTTP-level tests
- ✅ Default PH category seeding (22 categories) on signup
- ✅ Accounts, categories, transactions CRUD

**LLM stack:**
- ✅ `LLMProvider` Protocol (text, vision, structured) with Gemini implemented; Groq/Ollama stubs
- ✅ Custom SQLite tracer (one `LLMCall` row per call)
- ✅ Token-bucket rate limiter for free-tier limits
- ✅ Purpose-based router (categorization / qa / ocr / insights / parse_quickadd)

**AI features:**
- ✅ Quick-add: free text → structured draft + auto-categorization, with user override → few-shot store
- ✅ Receipt OCR: Gemini Vision + auto-resolved category and account suggestions
- ✅ CSV import: batch categorization (20 rows/LLM call), preview + commit flow
- ✅ NL Q&A: function-calling with 7 typed query primitives, planner → validator → execute → summarizer pipeline
- ✅ Budgets: CRUD + progress endpoint with linear projection to period end
- ✅ Monthly insights: scheduled cron (1st of month) + on-demand endpoint, grounded in real spending stats
- ✅ Anomaly detection: 3-month rolling baseline, z-score flagging, LLM-explained anomalies; daily cron

**Observability & ops:**
- ✅ Custom SQLite tracer captures every LLM call (purpose, provider, model, tokens, latency, success/error)
- ✅ `/admin/llm-stats` endpoint exposes per-provider/per-purpose aggregations + projected paid-tier cost
- ✅ Async token-bucket rate limiter respects free-tier limits
- ✅ Automatic retry with exponential backoff on 429/5xx
- ✅ APScheduler with two cron jobs (monthly insights, daily anomaly scan)

**Eval suite (the differentiator):**
- ✅ `eval_categorization` — 55 hand-labeled PH transactions, accuracy + per-category F1 + confusion matrix
- ✅ `eval_qa` — 30 Q/A pairs against a 500-transaction fixture, two-judge LLM-as-judge with agreement check
- ✅ `eval_ocr` — framework + ground-truth schema; drop your own receipt photos to populate
- ✅ `eval_insights` — synthetic anomaly fixture, LLM-judged hallucination check (does it cite only supplied numbers?)
- Reports written to `backend/evals/results/<eval>_<ts>.md` and `<eval>_latest.md`

**Tests (no API key required — LLMs are mocked):**
- **70/70 passing** across 17 test files
- Cross-user isolation tested at the HTTP layer
- Anomaly detection tested for: normal spending (no flag), 4× spike (flagged), thin-history skipping, idempotency
- Q&A tools tested for correct grouping, filtering, period boundaries, AND user-scope safety

**Deploy-ready:**
- `backend/Dockerfile` (multi-stage, uv-based, ~150MB final)
- `backend/fly.toml` (Singapore region, auto-stop, 1GB persistent volume)
- `.github/workflows/ci.yml` (ruff + mypy + pytest)
- `.github/workflows/evals.yml` (weekly Sunday eval run, manual trigger)
- `.github/workflows/deploy.yml` (auto-deploy backend on main)

## Running the eval suite

```bash
cd backend

# Categorization eval (~5 min on free tier — pacing for Gemini's 10/min limit)
uv run pytest evals/eval_categorization.py -m eval -v -s

# Q&A eval (~10 min — generates 500-txn fixture, runs 30 questions × 2 judges)
uv run pytest evals/eval_qa.py -m eval -v -s

# Insights eval (single synthetic dataset, ~30s)
uv run pytest evals/eval_insights.py -m eval -v -s

# OCR eval (skipped unless you've added receipts in evals/datasets/receipts/)
uv run pytest evals/eval_ocr.py -m eval -v -s
```

**Free-tier note:** Gemini 2.5 Flash has a 10 req/min and ~250 req/day free-tier ceiling. Running all evals back-to-back will exhaust the daily quota. Schedule one per day, or upgrade to paid (~$0.10 to run the full suite).

**Frontend (Next.js 14 + Tailwind + Recharts):**
- ✅ Landing page with peso-coin gradient hero + 6 feature cards
- ✅ Login / Signup with httpOnly cookie auth (JWT never reaches browser JS)
- ✅ Protected app shell — sidebar nav + mobile bottom nav
- ✅ Dashboard — net worth, monthly spend/income/savings rate, category donut, budget mini-progress, recent transactions, latest insight callout
- ✅ Transactions page — accounts strip, full transaction list with category emoji rows, add-account dialog
- ✅ Quick-add component — types-naturally → Gemini parse → confirmation chip
- ✅ Q&A chat page (ChatGPT-style) — prompt suggestions, animated typing, expandable tool-call traces
- ✅ Budgets page — color-coded progress bars (on-track/warning/over), projected end-of-period
- ✅ Insights page — monthly summaries with markdown rendering + anomaly cards with z-score badges
- ✅ Receipt upload — drag-drop + camera, vision-extracted draft confirmation, suggested category/account chips
- ✅ All 15 routes build clean (`npm run build` ✓)
- ✅ Dark mode by default, `font-feature-settings` for tabular nums on money

## Deployment

See [`DEPLOY.md`](DEPLOY.md) for the full walkthrough. Both paths are free-tier:

- **Backend** → Fly.io (Singapore region, persistent volume for SQLite + receipts)
- **Frontend** → Vercel (auto-deploys on git push)

Configs are in place: `backend/Dockerfile`, `backend/fly.toml`, `.github/workflows/{ci,evals,deploy}.yml`.

## Next (final polish)

- [ ] Run `fly launch` + `vercel` (15 min, see [`DEPLOY.md`](DEPLOY.md))
- [ ] Take dashboard + Q&A screenshots for the README
- [ ] Record a 2-min Loom: "type → parse → save → ask a question → snap a receipt"
- [ ] When daily Gemini quota refreshes, run `uv run pytest evals/eval_categorization.py -m eval -s` and paste the F1 number into this README

## Layout

```
kuwenta/
├── PRD.md
├── PLAN.md
├── backend/
│   ├── app/
│   │   ├── core/        # auth, security, deps
│   │   ├── models/      # SQLModel tables
│   │   ├── schemas/     # Pydantic request/response
│   │   ├── api/         # FastAPI routers
│   │   ├── services/    # business logic
│   │   ├── llm/
│   │   │   ├── providers/   # Gemini, Groq, Ollama
│   │   │   └── prompts/     # versioned prompt files
│   │   ├── tools/       # Q&A function-calling primitives
│   │   └── jobs/        # APScheduler tasks
│   ├── tests/
│   └── evals/           # categorization, Q&A, OCR, insights evals
└── frontend/            # Next.js 14
```

See [`PLAN.md`](PLAN.md) for phase-by-phase build order and architectural decisions.

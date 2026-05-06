# Evals

Eval suite is a first-class deliverable, not an afterthought. Four eval tracks:

| Eval | What it measures | Fixture |
|---|---|---|
| `eval_categorization.py` | accuracy + per-category F1 + confusion matrix | `datasets/categorization.jsonl` (50+ hand-labeled PH transactions) |
| `eval_qa.py` | Q&A correctness via LLM-as-judge with two-judge agreement | `datasets/qa_pairs.jsonl` (30+ Q/A pairs) against fixed 500-transaction fixture |
| `eval_ocr.py` | merchant fuzzy match, total within ₱1, category match, line-item recall | `datasets/receipts/` (10–20 images + ground truth JSON) |
| `eval_insights.py` | does the insight identify the right anomaly? are claims grounded? | `datasets/insights/` (synthetic datasets with known anomalies) |

## Running

Evals hit real LLM APIs and are slow. They are skipped by default via the `eval` pytest marker.

```bash
# Run all evals (requires GEMINI_API_KEY etc.)
uv run pytest evals/ -m eval

# Run one
uv run pytest evals/eval_categorization.py -m eval -v
```

CI runs the eval suite on a separate workflow (cron + manual trigger), not on every PR.

## Output

Each eval writes a markdown report to `results/<eval_name>_<timestamp>.md` with metrics, examples of failures, and (for categorization) a confusion matrix. The latest results are surfaced in the project README.

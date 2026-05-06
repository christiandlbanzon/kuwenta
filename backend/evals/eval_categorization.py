"""Categorization eval — accuracy + per-category F1 + confusion matrix.

Runs every example in `evals/datasets/categorization.jsonl` through the live
categorization service (with Gemini) and compares the predicted category against
the ground-truth label.

Run:
    uv run pytest evals/eval_categorization.py -m eval -v

Outputs a markdown report under `evals/results/categorization_<ts>.md` and an
`evals/results/categorization_latest.md` for README inclusion.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

import pytest

from app.services.categorization import categorize
from evals._common import EVAL_DATASETS, load_jsonl, make_eval_db, make_eval_user, write_report


@pytest.mark.eval
async def test_categorization_eval() -> None:
    factory = await make_eval_db()
    user, _acc, _cats = await make_eval_user(factory)

    examples = load_jsonl(EVAL_DATASETS / "categorization.jsonl")
    results: list[dict] = []

    async with factory() as session:
        # refresh user into this session
        from sqlmodel import select

        from app.models.user import User as UserModel

        user = (await session.exec(select(UserModel).where(UserModel.id == user.id))).first()
        assert user is not None

        for ex in examples:
            txn_type = ex.get("type", "expense")
            try:
                result = await categorize(
                    session,
                    user,
                    description=ex["text"],
                    merchant=ex.get("merchant"),
                    amount=Decimal(ex["amount"]),
                    txn_type=txn_type,
                )
                predicted = result.category_name
                confidence = result.confidence
            except Exception as e:
                predicted = f"ERROR: {type(e).__name__}"
                confidence = 0.0
            results.append(
                {
                    "text": ex["text"],
                    "expected": ex["category"],
                    "predicted": predicted,
                    "correct": predicted == ex["category"],
                    "confidence": confidence,
                }
            )

    # --- Compute metrics ---
    n = len(results)
    rate_limited = sum(
        1
        for r in results
        if "ClientError" in r["predicted"]
        or "ServerError" in r["predicted"]
        or "RESOURCE_EXHAUSTED" in r["predicted"]
    )
    if n and rate_limited / n > 0.5:
        pytest.skip(
            f"{rate_limited}/{n} calls failed with rate-limit/server errors. "
            f"Daily Gemini free-tier quota likely exhausted — re-run when quota refreshes."
        )
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / n if n else 0.0

    # Per-category precision/recall/F1
    by_label = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for r in results:
        if r["correct"]:
            by_label[r["expected"]]["tp"] += 1
        else:
            by_label[r["expected"]]["fn"] += 1
            by_label[r["predicted"]]["fp"] += 1

    f1_table: list[tuple[str, float, float, float, int]] = []
    for label, stats in sorted(by_label.items()):
        tp, fp, fn = stats["tp"], stats["fp"], stats["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        support = tp + fn
        if support > 0:
            f1_table.append((label, precision, recall, f1, support))

    macro_f1 = sum(row[3] for row in f1_table) / len(f1_table) if f1_table else 0.0

    # Confusion matrix (only for mispredictions, to keep it small)
    confusions = Counter(
        (r["expected"], r["predicted"]) for r in results if not r["correct"]
    )

    # --- Render report ---
    md: list[str] = []
    md.append("# Categorization eval\n")
    md.append(f"**Examples:** {n}  ")
    md.append(f"**Accuracy:** {accuracy:.2%}  ")
    md.append(f"**Macro F1:** {macro_f1:.3f}\n")
    md.append("## Per-category performance\n")
    md.append("| Category | Precision | Recall | F1 | Support |")
    md.append("|---|---:|---:|---:|---:|")
    for label, p, r, f, s in f1_table:
        md.append(f"| {label} | {p:.3f} | {r:.3f} | {f:.3f} | {s} |")
    md.append("")

    if confusions:
        md.append("## Mispredictions\n")
        md.append("| Expected | Predicted | Count |")
        md.append("|---|---|---:|")
        for (exp, pred), count in confusions.most_common():
            md.append(f"| {exp} | {pred} | {count} |")
        md.append("")
    else:
        md.append("## Mispredictions\n\n_(none — all examples correctly categorized)_\n")

    # Average confidence on correct vs wrong
    correct_conf = [r["confidence"] for r in results if r["correct"]]
    wrong_conf = [r["confidence"] for r in results if not r["correct"]]
    if correct_conf:
        md.append(f"**Avg confidence on correct:** {sum(correct_conf)/len(correct_conf):.3f}  ")
    if wrong_conf:
        md.append(f"**Avg confidence on wrong:** {sum(wrong_conf)/len(wrong_conf):.3f}\n")

    report_path = write_report("categorization", "\n".join(md))
    print(f"\n[eval_categorization] {accuracy:.1%} accuracy, macro F1 {macro_f1:.3f}")
    print(f"[eval_categorization] report: {report_path}")

    # Soft assertion — fail if accuracy regresses below a floor we expect Gemini to clear
    assert accuracy >= 0.70, f"Categorization accuracy regressed to {accuracy:.2%}"

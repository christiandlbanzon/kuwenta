"""OCR eval — metrics: merchant fuzzy match, total within ₱1, category exact, line items.

You provide receipts: drop images in `evals/datasets/receipts/` and add
ground-truth entries to `evals/datasets/receipts/ground_truth.jsonl`. See the README
in that directory for the schema.

Run:
    uv run pytest evals/eval_ocr.py -m eval -v

If `ground_truth.jsonl` is empty, the eval is skipped (still useful framework — fill
in your own receipts).
"""

from __future__ import annotations

from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

import pytest
from sqlmodel import select

from app.models.user import User as UserModel
from app.services.ocr import extract_receipt
from evals._common import EVAL_DATASETS, load_jsonl, make_eval_db, make_eval_user, write_report

RECEIPTS_DIR = EVAL_DATASETS / "receipts"
FUZZY_THRESHOLD = 0.8
TOTAL_TOLERANCE = Decimal("1.00")


def _fuzzy(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _ext_to_mime(p: Path) -> str:
    ext = p.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".heic": "image/heic"}.get(ext, "image/jpeg")


@pytest.mark.eval
async def test_ocr_eval() -> None:
    gt_path = RECEIPTS_DIR / "ground_truth.jsonl"
    if not gt_path.exists() or not gt_path.read_text(encoding="utf-8").strip():
        pytest.skip(
            "No receipts in evals/datasets/receipts/ground_truth.jsonl — "
            "add your own receipts to run this eval."
        )

    gts = load_jsonl(gt_path)
    factory = await make_eval_db()
    await make_eval_user(factory)

    correct_merchant = 0
    correct_total = 0
    correct_category = 0
    correct_payment = 0
    correct_line_items = 0
    failures: list[str] = []

    async with factory() as session:
        user = (
            await session.exec(select(UserModel).where(UserModel.email == "eval@kuwenta.dev"))
        ).first()
        assert user is not None

        for gt in gts:
            img_path = RECEIPTS_DIR / gt["image"]
            if not img_path.exists():
                failures.append(f"missing image: {img_path}")
                continue
            image_bytes = img_path.read_bytes()
            mime = _ext_to_mime(img_path)
            try:
                result = await extract_receipt(session, user, image_bytes, mime_type=mime)
            except Exception as e:
                failures.append(f"{gt['image']}: extraction error {e}")
                continue
            ext = result.extracted

            # Merchant
            if _fuzzy(ext.merchant, gt.get("merchant")) >= FUZZY_THRESHOLD:
                correct_merchant += 1
            else:
                failures.append(
                    f"{gt['image']}: merchant '{ext.merchant}' vs expected '{gt.get('merchant')}'"
                )

            # Total
            if "total" in gt and ext.total is not None:
                expected = Decimal(str(gt["total"]))
                if abs(ext.total - expected) <= TOTAL_TOLERANCE:
                    correct_total += 1
                else:
                    failures.append(
                        f"{gt['image']}: total {ext.total} vs expected {expected}"
                    )

            # Category
            if "category" in gt:
                if ext.category_guess == gt["category"]:
                    correct_category += 1

            # Payment method
            if "payment_method" in gt:
                if ext.payment_method == gt["payment_method"]:
                    correct_payment += 1

            # Line items
            if "min_line_items" in gt:
                if len(ext.line_items) >= gt["min_line_items"]:
                    correct_line_items += 1

    n = len(gts)
    md: list[str] = []
    md.append("# OCR eval\n")
    md.append(f"**Receipts:** {n}\n")
    md.append("| Metric | Score |")
    md.append("|---|---:|")
    md.append(f"| Merchant fuzzy match (≥ {FUZZY_THRESHOLD}) | {correct_merchant}/{n} ({correct_merchant/n:.1%}) |")
    if any("total" in gt for gt in gts):
        with_total = sum(1 for gt in gts if "total" in gt)
        md.append(f"| Total within ₱{TOTAL_TOLERANCE} | {correct_total}/{with_total} ({correct_total/with_total:.1%}) |")
    if any("category" in gt for gt in gts):
        with_cat = sum(1 for gt in gts if "category" in gt)
        md.append(f"| Category exact match | {correct_category}/{with_cat} ({correct_category/with_cat:.1%}) |")
    if any("payment_method" in gt for gt in gts):
        with_pm = sum(1 for gt in gts if "payment_method" in gt)
        md.append(f"| Payment method exact match | {correct_payment}/{with_pm} ({correct_payment/with_pm:.1%}) |")
    if any("min_line_items" in gt for gt in gts):
        with_li = sum(1 for gt in gts if "min_line_items" in gt)
        md.append(f"| Line items ≥ expected | {correct_line_items}/{with_li} ({correct_line_items/with_li:.1%}) |")

    if failures:
        md.append("\n## Failures\n")
        for f in failures[:20]:
            md.append(f"- {f}")

    report_path = write_report("ocr", "\n".join(md))
    print(f"\n[eval_ocr] {n} receipts; merchant {correct_merchant}/{n}, total {correct_total}/{n}")
    print(f"[eval_ocr] report: {report_path}")

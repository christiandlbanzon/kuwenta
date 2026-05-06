"""Receipt OCR service.

Pipeline:
    1. Save the uploaded image bytes to `<RECEIPT_STORAGE_DIR>/<user_id>/<uuid>.<ext>`.
    2. Call the vision provider with the ocr_receipt prompt + image bytes; get a
       ReceiptExtraction (constrained schema).
    3. Resolve `category_guess` -> category_id and `payment_method` hint -> account_id.
    4. Persist a `Receipt` row referencing the file + raw extraction. Transaction is
       NOT created automatically — the frontend shows a draft for the user to confirm,
       then POSTs /transactions to persist (and patches the Receipt with the txn id).
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.config import get_settings
from app.llm.base import Message
from app.llm.prompts import load_prompt
from app.llm.router import get_provider_for_purpose
from app.llm.tracer import trace
from app.models.account import Account
from app.models.category import Category
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.receipts import ReceiptExtraction, ReceiptUploadResponse

# Map LLM-extracted payment_method to the Account.type / institution we'll match.
_PAYMENT_TO_ACCOUNT_HINTS: dict[str, tuple[str | None, list[str]]] = {
    "gcash":         ("ewallet",     ["gcash"]),
    "maya":          ("ewallet",     ["maya", "paymaya"]),
    "paymaya":       ("ewallet",     ["maya", "paymaya"]),
    "cash":          ("cash",        []),
    "credit_card":   ("credit_card", []),
    "debit_card":    ("bank",        []),
    "bank_transfer": ("bank",        []),
    "other":         (None,          []),
}


def _ext_for_mime(mime: str) -> str:
    if mime in ("image/jpeg", "image/jpg"):
        return "jpg"
    if mime == "image/png":
        return "png"
    if mime == "image/webp":
        return "webp"
    if mime == "image/heic":
        return "heic"
    return "bin"


def _save_image(user_id: UUID, image_bytes: bytes, mime_type: str) -> Path:
    settings = get_settings()
    base = Path(settings.receipt_storage_dir) / str(user_id)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{uuid4()}.{_ext_for_mime(mime_type)}"
    path.write_bytes(image_bytes)
    return path


async def _resolve_category(
    session: AsyncSession, user_id: UUID, name: str | None
) -> UUID | None:
    if not name:
        return None
    res = await session.exec(
        select(Category).where(
            Category.user_id == user_id, Category.name == name
        )
    )
    cat = res.first()
    return cat.id if cat else None


async def _resolve_account(
    session: AsyncSession, user_id: UUID, payment_method: str | None
) -> UUID | None:
    if not payment_method:
        return None
    type_hint, institution_hints = _PAYMENT_TO_ACCOUNT_HINTS.get(
        payment_method, (None, [])
    )
    if type_hint is None and not institution_hints:
        return None
    accs = (
        await session.exec(select(Account).where(Account.user_id == user_id))
    ).all()
    # Prefer institution match if we have hints
    if institution_hints:
        for a in accs:
            inst = (a.institution or "").lower()
            name = a.name.lower()
            if any(h in inst or h in name for h in institution_hints):
                return a.id
    if type_hint:
        for a in accs:
            if a.type == type_hint:
                return a.id
    return None


async def extract_receipt(
    session: AsyncSession,
    user: User,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> ReceiptUploadResponse:
    # 1. Save image
    image_path = _save_image(user.id, image_bytes, mime_type)

    # 2. Build prompt with user's categories
    cats = (
        await session.exec(select(Category).where(Category.user_id == user.id))
    ).all()
    categories_block = "\n".join(f"- {c.name}" for c in cats)
    prompt_template = load_prompt("ocr_receipt")
    system_prompt = prompt_template.format(categories_block=categories_block)

    # 3. Call vision provider
    # We use complete_with_vision and parse the JSON ourselves, since structured-output
    # + vision in one call isn't uniformly supported across providers. The prompt
    # already constrains the model to return JSON.
    provider = get_provider_for_purpose("ocr")
    async with trace(
        session,
        user_id=user.id,
        purpose="ocr",
        provider=provider.name,
        model=provider.default_model,
    ) as t:
        completion = await provider.complete_with_vision(
            [
                Message(role="system", content=system_prompt),
                Message(role="user", content="Extract the receipt fields as JSON."),
            ],
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
        t.tokens(completion.input_tokens, completion.output_tokens)

    extraction = _parse_extraction(completion.text)

    # 4. Resolve hints
    cat_id = await _resolve_category(session, user.id, extraction.category_guess)
    acc_id = await _resolve_account(session, user.id, extraction.payment_method)

    # 5. Persist Receipt row (transaction is created later, on user confirmation)
    receipt = Receipt(
        user_id=user.id,
        image_path=str(image_path),
        extracted_data=extraction.model_dump(mode="json"),
    )
    session.add(receipt)
    await session.commit()
    await session.refresh(receipt)

    return ReceiptUploadResponse(
        receipt_id=receipt.id,
        image_path=str(image_path),
        extracted=extraction,
        suggested_category_id=cat_id,
        suggested_account_id=acc_id,
    )


def _parse_extraction(text: str) -> ReceiptExtraction:
    """Best-effort parse — the prompt asks for JSON. If the model wrapped it in markdown
    fences or added prose, strip those before validating."""
    import json
    import re

    s = text.strip()
    # Strip ```json ... ``` fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # Find the first {...} block
    if not s.startswith("{"):
        match = re.search(r"\{.*\}", s, flags=re.DOTALL)
        s = match.group(0) if match else "{}"
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        data = {}
    return ReceiptExtraction.model_validate(data)

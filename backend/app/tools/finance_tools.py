"""Q&A function-calling tools.

Each tool is a typed Python function with a Pydantic args schema. The Q&A planner LLM
sees the tool catalog (JSON schema + docstring) and picks tools + arguments. The
dispatcher (`execute_tool`) validates the tool name against the whitelist, validates
arguments against the per-tool schema, then executes a parameterized query scoped to
the calling user's id.

Why function-calling and not LLM-generated SQL: smaller attack surface (no SQL injection
to harden against), every tool call is directly evaluable (we can assert the right tool
was chosen with the right args), and results are structured so the summarizer LLM has a
clean object to format rather than free-text.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.account import Account
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction

# --- Common types -----------------------------------------------------------

PeriodKind = Literal[
    "this_month",
    "last_month",
    "this_year",
    "last_7_days",
    "last_30_days",
    "custom",
]

TxnTypeLit = Literal["expense", "income", "transfer"]


class Period(BaseModel):
    kind: PeriodKind
    start: date | None = Field(None, description="Required when kind='custom'")
    end: date | None = Field(None, description="Required when kind='custom'")


# --- Tool argument schemas --------------------------------------------------


class SumByCategoryArgs(BaseModel):
    """Total spent (or earned) per category over a period. Optionally filter to one category."""

    period: Period
    category_name: str | None = Field(None, description="Optional — restrict to one category")
    transaction_type: Literal["expense", "income"] = "expense"


class SumByMerchantArgs(BaseModel):
    """Total per merchant over a period (top N)."""

    period: Period
    top_n: int = Field(10, ge=1, le=50)
    transaction_type: Literal["expense", "income"] = "expense"


class TransactionsFilterArgs(BaseModel):
    """List transactions matching filters (most recent first)."""

    period: Period
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    category_name: str | None = None
    merchant_substring: str | None = None
    transaction_type: TxnTypeLit | None = None
    limit: int = Field(50, ge=1, le=200)


class ComparePeriodsArgs(BaseModel):
    """Compare spending in a category across two periods."""

    category_name: str
    period_a: Period
    period_b: Period
    transaction_type: Literal["expense", "income"] = "expense"


class BudgetStatusArgs(BaseModel):
    """How a budget is tracking: spent vs. budgeted, projected end-of-period."""

    category_name: str
    period: Period


class TopCategoriesArgs(BaseModel):
    """Top N categories by total over a period."""

    period: Period
    n: int = Field(5, ge=1, le=20)
    transaction_type: Literal["expense", "income"] = "expense"


class AccountBalancesArgs(BaseModel):
    """Current balance per account."""


# --- Tool registry ----------------------------------------------------------

TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "sum_by_category": SumByCategoryArgs,
    "sum_by_merchant": SumByMerchantArgs,
    "transactions_filter": TransactionsFilterArgs,
    "compare_periods": ComparePeriodsArgs,
    "budget_status": BudgetStatusArgs,
    "top_categories": TopCategoriesArgs,
    "account_balances": AccountBalancesArgs,
}

ToolName = Literal[
    "sum_by_category",
    "sum_by_merchant",
    "transactions_filter",
    "compare_periods",
    "budget_status",
    "top_categories",
    "account_balances",
]


def _gemini_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic schema to the function-declaration shape Gemini expects.

    Strips JSON Schema features Gemini doesn't support ($defs, $ref) by inlining,
    and removes Pydantic-specific keys like `title`.
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def _inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                return _inline(defs.get(ref, {}))
            return {k: _inline(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [_inline(x) for x in node]
        return node

    inlined = _inline(raw)
    inlined.pop("title", None)
    return inlined


def tool_schemas_for_planner() -> list[dict[str, Any]]:
    """Return JSON schemas for all tools in OpenAI/Gemini function-calling format."""
    out: list[dict[str, Any]] = []
    for name, schema_cls in TOOL_SCHEMAS.items():
        params = _gemini_schema(schema_cls)
        out.append(
            {
                "name": name,
                "description": (schema_cls.__doc__ or "").strip(),
                "parameters": params,
            }
        )
    return out


# --- Tool implementations ---------------------------------------------------


async def _resolve_period_dt(period: Period, timezone: str) -> tuple[datetime, datetime]:
    # Lazy import avoids a circular dep — _periods imports Period from this module.
    from app.tools._periods import resolve_period

    return resolve_period(period, timezone=timezone)


async def _category_id_for_name(
    session: AsyncSession, user_id: UUID, name: str
) -> UUID | None:
    res = await session.exec(
        select(Category.id).where(
            Category.user_id == user_id, func.lower(Category.name) == name.lower()
        )
    )
    return res.first()


async def sum_by_category(
    args: SumByCategoryArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    start, end = await _resolve_period_dt(args.period, timezone)
    stmt = (
        select(
            Category.name.label("category"),  # type: ignore[attr-defined]
            func.sum(Transaction.amount).label("total"),
            func.count().label("count"),
        )
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == args.transaction_type,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    if args.category_name:
        stmt = stmt.where(func.lower(Category.name) == args.category_name.lower())
    rows = (await session.exec(stmt)).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "transaction_type": args.transaction_type,
        "totals": [
            {
                "category": r.category,
                "total": str(r.total or Decimal("0")),
                "count": int(r.count),
            }
            for r in rows
        ],
    }


async def sum_by_merchant(
    args: SumByMerchantArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    start, end = await _resolve_period_dt(args.period, timezone)
    stmt = (
        select(
            Transaction.merchant.label("merchant"),  # type: ignore[attr-defined]
            func.sum(Transaction.amount).label("total"),
            func.count().label("count"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.type == args.transaction_type,
            Transaction.merchant.is_not(None),  # type: ignore[attr-defined]
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        .group_by(Transaction.merchant)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(args.top_n)
    )
    rows = (await session.exec(stmt)).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "transaction_type": args.transaction_type,
        "merchants": [
            {"merchant": r.merchant, "total": str(r.total or Decimal("0")), "count": int(r.count)}
            for r in rows
        ],
    }


async def transactions_filter(
    args: TransactionsFilterArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    start, end = await _resolve_period_dt(args.period, timezone)
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.occurred_at >= start,
        Transaction.occurred_at <= end,
    )
    if args.transaction_type:
        stmt = stmt.where(Transaction.type == args.transaction_type)
    if args.min_amount is not None:
        stmt = stmt.where(Transaction.amount >= args.min_amount)
    if args.max_amount is not None:
        stmt = stmt.where(Transaction.amount <= args.max_amount)
    if args.merchant_substring:
        stmt = stmt.where(
            func.lower(Transaction.merchant).contains(args.merchant_substring.lower())  # type: ignore[attr-defined]
        )
    if args.category_name:
        cat_id = await _category_id_for_name(session, user_id, args.category_name)
        if cat_id is None:
            return {
                "period": {"start": start.isoformat(), "end": end.isoformat()},
                "transactions": [],
                "note": f"No category named '{args.category_name}' found.",
            }
        stmt = stmt.where(Transaction.category_id == cat_id)
    stmt = stmt.order_by(Transaction.occurred_at.desc()).limit(args.limit)  # type: ignore[attr-defined]
    rows = (await session.exec(stmt)).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "transactions": [
            {
                "id": str(t.id),
                "occurred_at": t.occurred_at.isoformat(),
                "amount": str(t.amount),
                "type": t.type,
                "description": t.description,
                "merchant": t.merchant,
                "category_id": str(t.category_id) if t.category_id else None,
            }
            for t in rows
        ],
    }


async def compare_periods(
    args: ComparePeriodsArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    cat_id = await _category_id_for_name(session, user_id, args.category_name)
    if cat_id is None:
        return {
            "category": args.category_name,
            "transaction_type": args.transaction_type,
            "note": f"No category named '{args.category_name}' found.",
        }

    async def _sum(period: Period) -> Decimal:
        start, end = await _resolve_period_dt(period, timezone)
        stmt = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == cat_id,
            Transaction.type == args.transaction_type,
            Transaction.occurred_at >= start,
            Transaction.occurred_at <= end,
        )
        result = (await session.exec(stmt)).first()
        return result or Decimal("0")

    a_total = await _sum(args.period_a)
    b_total = await _sum(args.period_b)
    diff = a_total - b_total
    pct = float(diff / b_total * 100) if b_total else None
    return {
        "category": args.category_name,
        "transaction_type": args.transaction_type,
        "period_a_total": str(a_total),
        "period_b_total": str(b_total),
        "difference": str(diff),
        "percent_change_vs_b": pct,
    }


async def budget_status(
    args: BudgetStatusArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    cat_id = await _category_id_for_name(session, user_id, args.category_name)
    if cat_id is None:
        return {"category": args.category_name, "note": "Category not found."}

    budget_row = (
        await session.exec(
            select(Budget).where(
                Budget.user_id == user_id,
                Budget.category_id == cat_id,
                Budget.is_active.is_(True),  # type: ignore[attr-defined]
            )
        )
    ).first()

    start, end = await _resolve_period_dt(args.period, timezone)
    spent_row = (
        await session.exec(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.category_id == cat_id,
                Transaction.type == "expense",
                Transaction.occurred_at >= start,
                Transaction.occurred_at <= end,
            )
        )
    ).first()
    spent = spent_row or Decimal("0")

    out: dict[str, Any] = {
        "category": args.category_name,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "spent": str(spent),
    }
    if budget_row:
        out["budgeted"] = str(budget_row.amount)
        out["remaining"] = str(budget_row.amount - spent)
        out["percent_used"] = (
            float(spent / budget_row.amount * 100) if budget_row.amount else None
        )
        out["budget_period"] = budget_row.period
    else:
        out["note"] = "No active budget for this category."
    return out


async def top_categories(
    args: TopCategoriesArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    sub_args = SumByCategoryArgs(
        period=args.period, transaction_type=args.transaction_type, category_name=None
    )
    full = await sum_by_category(sub_args, user_id=user_id, session=session, timezone=timezone)
    full["totals"] = full["totals"][: args.n]
    full["n"] = args.n
    return full


async def account_balances(
    args: AccountBalancesArgs, *, user_id: UUID, session: AsyncSession, timezone: str
) -> dict[str, Any]:
    rows = (
        await session.exec(select(Account).where(Account.user_id == user_id))
    ).all()
    return {
        "accounts": [
            {
                "name": a.name,
                "type": a.type,
                "institution": a.institution,
                "balance": str(a.current_balance),
            }
            for a in rows
        ],
        "total": str(sum((a.current_balance for a in rows), Decimal("0"))),
    }


# --- Dispatcher -------------------------------------------------------------

_EXECUTORS: dict[str, Callable[..., Any]] = {
    "sum_by_category": sum_by_category,
    "sum_by_merchant": sum_by_merchant,
    "transactions_filter": transactions_filter,
    "compare_periods": compare_periods,
    "budget_status": budget_status,
    "top_categories": top_categories,
    "account_balances": account_balances,
}


class ToolValidationError(Exception):
    """Raised when an LLM-proposed tool call fails the whitelist or schema check."""


async def execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    user_id: UUID,
    session: AsyncSession,
    timezone: str = "Asia/Manila",
) -> dict[str, Any]:
    """Validate name + args, then dispatch. Always scoped to user_id."""
    if name not in TOOL_SCHEMAS:
        raise ToolValidationError(f"Unknown tool: {name!r}")
    schema_cls = TOOL_SCHEMAS[name]
    try:
        validated = schema_cls.model_validate(args)
    except Exception as e:
        raise ToolValidationError(f"Invalid args for {name}: {e}") from e
    executor = _EXECUTORS[name]
    return await executor(validated, user_id=user_id, session=session, timezone=timezone)

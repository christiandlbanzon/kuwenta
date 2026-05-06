from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.budgets import BudgetCreate, BudgetProgress, BudgetPublic, BudgetUpdate
from app.services import budgets as svc

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetPublic])
async def list_budgets(user: CurrentUser, session: SessionDep) -> list[BudgetPublic]:
    rows = await svc.list_budgets(session, user.id)
    return [BudgetPublic.model_validate(b, from_attributes=True) for b in rows]


@router.post("", response_model=BudgetPublic, status_code=status.HTTP_201_CREATED)
async def create_budget(
    payload: BudgetCreate, user: CurrentUser, session: SessionDep
) -> BudgetPublic:
    try:
        b = await svc.create_budget(session, user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return BudgetPublic.model_validate(b, from_attributes=True)


@router.patch("/{budget_id}", response_model=BudgetPublic)
async def update_budget(
    budget_id: UUID, payload: BudgetUpdate, user: CurrentUser, session: SessionDep
) -> BudgetPublic:
    b = await svc.update_budget(session, user.id, budget_id, payload)
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")
    return BudgetPublic.model_validate(b, from_attributes=True)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: UUID, user: CurrentUser, session: SessionDep
) -> None:
    ok = await svc.delete_budget(session, user.id, budget_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Budget not found")


@router.get("/progress", response_model=list[BudgetProgress])
async def progress(user: CurrentUser, session: SessionDep) -> list[BudgetProgress]:
    """Spending vs budget for the current period, with linear projection to period end."""
    return await svc.progress_for_user(session, user)

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.categories import CategoryCreate, CategoryPublic, CategoryUpdate
from app.services import categories as svc

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
async def list_categories(user: CurrentUser, session: SessionDep) -> list[CategoryPublic]:
    cats = await svc.list_categories(session, user.id)
    return [CategoryPublic.model_validate(c, from_attributes=True) for c in cats]


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate, user: CurrentUser, session: SessionDep
) -> CategoryPublic:
    cat = await svc.create_category(session, user.id, payload)
    return CategoryPublic.model_validate(cat, from_attributes=True)


@router.patch("/{category_id}", response_model=CategoryPublic)
async def update_category(
    category_id: UUID, payload: CategoryUpdate, user: CurrentUser, session: SessionDep
) -> CategoryPublic:
    cat = await svc.update_category(session, user.id, category_id, payload)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoryPublic.model_validate(cat, from_attributes=True)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID, user: CurrentUser, session: SessionDep
) -> None:
    ok = await svc.delete_category(session, user.id, category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Category not found")

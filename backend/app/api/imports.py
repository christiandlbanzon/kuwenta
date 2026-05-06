from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.deps import CurrentUser, SessionDep
from app.schemas.imports import CSVImportCommit, CSVImportPreview, CSVImportResult
from app.services.csv_import import commit_import, preview_import

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_BYTES = 2 * 1024 * 1024  # 2 MB CSV


@router.post("/csv/preview", response_model=CSVImportPreview)
async def csv_preview(
    user: CurrentUser,
    session: SessionDep,
    account_id: Annotated[UUID, Form(...)],
    file: UploadFile = File(...),
) -> CSVImportPreview:
    """Parse and categorize a CSV. Returns one row per CSV line — flagged rows
    (low-confidence categorization or parse errors) need user review before commit."""
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV too large (max 2 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return await preview_import(session, user, account_id=account_id, csv_bytes=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/csv/commit", response_model=CSVImportResult)
async def csv_commit(
    payload: CSVImportCommit, user: CurrentUser, session: SessionDep
) -> CSVImportResult:
    """Persist user-confirmed rows. The frontend may have edited categories or removed
    rows from the preview before sending."""
    try:
        return await commit_import(
            session, user, account_id=payload.account_id, rows=payload.rows
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

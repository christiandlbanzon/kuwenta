from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.receipts import ReceiptUploadResponse
from app.services.ocr import extract_receipt

router = APIRouter(prefix="/receipts", tags=["receipts"])

ACCEPTED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic"}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post(
    "/upload",
    response_model=ReceiptUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_receipt(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
) -> ReceiptUploadResponse:
    """Upload a receipt photo. Saves the image, runs Gemini Vision OCR, returns a
    draft for the user to confirm. The draft includes suggested category and account
    based on the merchant + payment method on the receipt."""
    if file.content_type not in ACCEPTED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type: {file.content_type}. "
            f"Supported: {sorted(ACCEPTED_MIME)}",
        )
    image_bytes = await file.read()
    if len(image_bytes) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 8 MB)")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    return await extract_receipt(
        session, user, image_bytes, mime_type=file.content_type or "image/jpeg"
    )

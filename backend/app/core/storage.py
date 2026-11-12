import hashlib
from pathlib import Path
import re
import uuid

from fastapi import HTTPException, UploadFile, status

from ..config import get_settings

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".docx", ".png", ".jpg", ".jpeg"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "application/octet-stream",
}


def sanitize_filename(filename: str) -> str:
    base = Path(filename or "document.txt").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    return cleaned[:120] or "document.txt"


async def save_tenant_upload(
    *,
    tenant_id: uuid.UUID,
    rental_id: uuid.UUID,
    doc_id: uuid.UUID,
    upload: UploadFile,
) -> tuple[str, str, int, str]:
    """
    Persist uploaded file strictly inside <UPLOAD_ROOT>/<tenant_id>/<rental_id>/
    with extension/size checks, traversal verification, and SHA-256 checksum.
    """
    settings = get_settings()
    safe_name = sanitize_filename(upload.filename or "upload.pdf")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if upload.content_type and upload.content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME content-type '{upload.content_type}'",
        )

    raw_bytes = await upload.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max limit of {settings.MAX_UPLOAD_MB} MB",
        )

    # Magic-byte sanity check for PDFs
    if ext == ".pdf" and not raw_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF header magic bytes",
        )

    # Active malicious document / exploit / indirect-injection scan prior to persistence
    from ..runtime.document_security import inspect_document_bytes

    sec_check = inspect_document_bytes(
        raw_bytes,
        filename=safe_name,
        mime_type=upload.content_type or "",
        allow_indirect_text_neutralization=False,
    )
    if not sec_check.is_safe_for_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sec_check.blocked_reason,
        )

    root = settings.upload_root_path
    target_dir = (root / str(tenant_id) / str(rental_id)).resolve()
    if not target_dir.is_relative_to(root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant upload target path",
        )
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = (target_dir / f"{doc_id}_{safe_name}").resolve()
    if not target_file.is_relative_to(target_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal attempt rejected",
        )

    target_file.write_bytes(raw_bytes)
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    rel_path = target_file.relative_to(root).as_posix()
    return rel_path, checksum, len(raw_bytes), safe_name


def resolve_tenant_file(tenant_id: uuid.UUID, rel_path: str) -> Path:
    """Resolve and strictly verify a file path belongs to the authenticated tenant."""
    settings = get_settings()
    root = settings.upload_root_path
    tenant_root = (root / str(tenant_id)).resolve()
    target = (root / rel_path).resolve()
    if not target.is_relative_to(tenant_root) or not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in authenticated tenant storage",
        )
    return target

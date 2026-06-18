import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.models.schemas import UploadResponse
from backend.models.database import get_db
from backend.models.documents import Document

router = APIRouter()

MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """上传文件，保存后异步派发 Celery 任务处理"""
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    doc_id = uuid.uuid4()
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(doc_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_size=len(contents),
        file_path=file_path,
        status="pending",
        source_type="uploaded",
    )
    db.add(doc)
    await db.commit()

    from backend.core.tasks import process_document
    process_document.delay(str(doc_id), file_path)

    return UploadResponse(
        message="文件已接收，后台处理中",
        doc_id=str(doc_id),
        collection_id="default",
        text_chunks=0,
        images=0,
    )

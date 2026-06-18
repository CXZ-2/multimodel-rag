import os
import uuid
import shutil
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.config import settings
from backend.models.database import get_db
from backend.models.documents import Document
from backend.models.schemas import DocumentOut, DocumentListOut, DocumentStatusOut
from backend.core.tasks import process_document
from backend.core.redis_client import clear_cache


class BatchDeleteRequest(BaseModel):
    ids: list[str]

router = APIRouter()
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/documents/upload", response_model=list[DocumentOut])
async def upload_documents(files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)):
    results = []
    for file in files:
        doc_id = uuid.uuid4()
        upload_dir = os.path.join(settings.UPLOAD_DIR, str(doc_id))
        os.makedirs(upload_dir, exist_ok=True)

        contents = await file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(413, f"{file.filename} 超过大小限制")

        pdf_path = os.path.join(upload_dir, file.filename)
        with open(pdf_path, "wb") as f:
            f.write(contents)

        doc = Document(
            id=doc_id,
            filename=file.filename,
            file_size=len(contents),
            file_path=pdf_path,
            status="pending",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        ext = os.path.splitext(file.filename)[1].lower()
        if ext == ".pdf":
            import fitz
            pdf_doc = fitz.open(pdf_path)
            full_text = "\n".join(page.get_text() for page in pdf_doc)
            pdf_doc.close()
        else:
            full_text = ""
        process_document.delay(str(doc.id), pdf_path)

        results.append(doc)

    return results


@router.get("/documents", response_model=DocumentListOut)
async def list_documents(
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Document).order_by(Document.uploaded_at.desc())
    count_q = select(func.count(Document.id))
    if status:
        q = q.where(Document.status == status)
        count_q = count_q.where(Document.status == status)
    if source_type:
        q = q.where(Document.source_type == source_type)
        count_q = count_q.where(Document.source_type == source_type)

    total = (await db.execute(count_q)).scalar()
    offset = (page - 1) * page_size
    rows = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()
    return DocumentListOut(items=list(rows), total=total)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    return DocumentOut(
        id=str(doc.id),
        filename=doc.filename,
        file_size=doc.file_size,
        status=doc.status,
        text_chunks=doc.text_chunks,
        image_count=doc.image_count,
        cleaning_report=doc.cleaning_report or {},
        source_url=doc.source_url,
        source_type=doc.source_type or "uploaded",
        uploaded_at=doc.uploaded_at,
    )


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusOut)
async def get_document_status(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    return DocumentStatusOut(
        id=str(doc.id),
        status=doc.status,
        text_chunks=doc.text_chunks,
        image_count=doc.image_count,
        error_message=doc.error_message,
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    from backend.core import vectorstore

    doc = await db.get(Document, doc_id)
    if not doc:
        # 文档在 PG 中已不存在，但从 Milvus 中清理残留数据
        try:
            vectorstore.delete_collection(str(doc_id))
        except Exception:
            pass
        clear_cache()
        return {"ok": True}

    upload_dir = os.path.dirname(doc.file_path)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

    await db.delete(doc)
    await db.commit()
    # 同步删除 Milvus 中的向量数据
    try:
        vectorstore.delete_collection(str(doc_id))
    except Exception:
        pass
    clear_cache()
    return {"ok": True}


@router.post("/documents/batch-delete")
async def batch_delete_documents(req: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    """批量删除文档"""
    from uuid import UUID
    errors = []
    deleted = 0

    # 解析所有 UUID 并一次查询所有文档
    uuids: list[UUID] = []
    for id_str in req.ids:
        try:
            uuids.append(UUID(id_str))
        except ValueError:
            errors.append(f"无效 ID: {id_str}")

    if uuids:
        rows = await db.execute(select(Document).where(Document.id.in_(uuids)))
        docs = {str(d.id): d for d in rows.scalars().all()}

        for id_str in req.ids:
            if id_str not in docs:
                errors.append(f"文档不存在: {id_str}")
                continue
            doc = docs[id_str]
            upload_dir = os.path.dirname(doc.file_path)
            if os.path.exists(upload_dir):
                shutil.rmtree(upload_dir)
            await db.delete(doc)
            deleted += 1
            # 同步清理 Milvus + BM25
            try:
                vectorstore.delete_collection(id_str)
            except Exception:
                pass
            try:
                from backend.core.bm25_index import remove_doc
                remove_doc(id_str)
            except Exception:
                pass

    await db.commit()
    clear_cache()
    return {"ok": True, "deleted": deleted, "errors": errors}

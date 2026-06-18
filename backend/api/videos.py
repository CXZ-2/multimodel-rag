"""视频 API — 上传、状态查询、生成、列表、删除"""
import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.config import settings
from backend.models.database import get_db
from backend.models.documents import Document
from backend.models.schemas import (
    VideoUploadResponse, VideoStatusOut, VideoOut, VideoListOut,
    VideoGenerateRequest, VideoGenerateResponse, VideoGenerateStatusOut,
)
from backend.core.tasks import process_video
from backend.core.video_generator import generate_video, query_task
from backend.core.redis_client import clear_cache

router = APIRouter()
MAX_VIDEO_SIZE = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}


@router.post("/videos/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(400, f"不支持的视频格式: {ext}，支持: {', '.join(VIDEO_EXTS)}")

    contents = await file.read()
    if len(contents) > MAX_VIDEO_SIZE:
        raise HTTPException(413, f"{file.filename} 超过大小限制 ({settings.MAX_VIDEO_SIZE_MB}MB)")

    doc_id = uuid.uuid4()
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(doc_id))
    os.makedirs(upload_dir, exist_ok=True)

    video_path = os.path.join(upload_dir, file.filename)
    with open(video_path, "wb") as f:
        f.write(contents)

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_size=len(contents),
        file_path=video_path,
        status="pending",
        source_type="video",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    process_video.delay(str(doc.id), video_path)

    return VideoUploadResponse(message="视频已接收，后台处理中", doc_id=str(doc.id))


@router.get("/videos/{doc_id}/status", response_model=VideoStatusOut)
async def get_video_status(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "视频不存在")
    report = doc.cleaning_report or {}
    return VideoStatusOut(
        id=str(doc.id),
        status=doc.status,
        duration=doc.duration,
        transcript=report.get("transcript", ""),
        description=report.get("summary", ""),
        error_message=doc.error_message,
    )


@router.get("/videos", response_model=VideoListOut)
async def list_videos(
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Document).where(
        Document.source_type.in_(["video", "generated_video"])
    ).order_by(Document.uploaded_at.desc())
    count_q = select(func.count(Document.id)).where(
        Document.source_type.in_(["video", "generated_video"])
    )

    if status:
        q = q.where(Document.status == status)
        count_q = count_q.where(Document.status == status)
    if source_type:
        q = q.where(Document.source_type == source_type)
        count_q = count_q.where(Document.source_type == source_type)

    total = (await db.execute(count_q)).scalar()
    offset = (page - 1) * page_size
    rows = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()

    items = [VideoOut(
        id=str(d.id), filename=d.filename, file_size=d.file_size,
        duration=d.duration, status=d.status, source_type=d.source_type,
        understanding=d.cleaning_report, uploaded_at=d.uploaded_at,
    ) for d in rows]
    return VideoListOut(items=items, total=total)


@router.delete("/videos/{doc_id}")
async def delete_video(doc_id: str, db: AsyncSession = Depends(get_db)):
    from backend.core import vectorstore

    doc = await db.get(Document, doc_id)
    if not doc:
        try:
            vectorstore.delete_collection(doc_id)
        except Exception:
            pass
        clear_cache()
        return {"ok": True}

    upload_dir = os.path.dirname(doc.file_path)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)

    await db.delete(doc)
    await db.commit()

    try:
        vectorstore.delete_collection(doc_id)
    except Exception:
        pass
    clear_cache()
    return {"ok": True}


@router.post("/videos/generate", response_model=VideoGenerateResponse)
async def create_video_generation(req: VideoGenerateRequest, db: AsyncSession = Depends(get_db)):
    try:
        task_id = generate_video(
            prompt=req.prompt, model=req.model, resolution=req.resolution,
            ratio=req.ratio, duration=req.duration, negative_prompt=req.negative_prompt,
        )
    except Exception as e:
        raise HTTPException(400, f"视频生成失败: {str(e)}")

    doc = Document(
        id=uuid.uuid4(),
        filename=f"generated_{task_id[:8]}.mp4",
        file_size=0,
        file_path="",
        status="generating",
        source_type="generated_video",
        source_url=f"task://{task_id}",
        cleaning_report={
            "generation_prompt": req.prompt,
            "generation_model": req.model,
            "resolution": req.resolution,
            "ratio": req.ratio,
            "duration": req.duration,
        },
    )
    db.add(doc)
    await db.commit()

    return VideoGenerateResponse(task_id=task_id, status="PENDING")


@router.get("/videos/generate/{task_id}", response_model=VideoGenerateStatusOut)
async def get_generation_status(task_id: str, model: str = Query("wanx2.1-t2v-turbo")):
    result = query_task(task_id, model=model)
    return VideoGenerateStatusOut(**result)


@router.get("/videos/proxy")
async def proxy_video(url: str = Query(...)):
    """代理外部视频 URL，解决 CORS 跨域问题"""
    import httpx
    from fastapi.responses import StreamingResponse

    async def stream():
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", url, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    yield b""
                    return
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    yield chunk

    ext = url.split("?")[0].split(".")[-1].lower()
    mime = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}.get(ext, "video/mp4")
    return StreamingResponse(stream(), media_type=mime, headers={"Accept-Ranges": "bytes"})

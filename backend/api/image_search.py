"""以图搜图 API"""
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.documents import Document
from backend.models.schemas import ImageSearchRequest, ImageSearchResponse, ImageSearchResult
from backend.config import settings
from backend.core import retriever

router = APIRouter()


def _to_api_url(file_path: str) -> str:
    """将 Docker 内部路径转为 API URL: /app/uploads/<doc_id>/... → /api/images/<doc_id>/..."""
    if not file_path:
        return ""
    # 提取 uploads/<doc_id>/... 部分
    m = re.search(r'uploads/(.+)', file_path)
    if m:
        return f"/api/images/{m.group(1)}"
    # 回退: 直接用最后两段路径
    parts = file_path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return f"/api/images/{parts[-2]}/{parts[-1]}"
    return file_path


@router.get("/images/{doc_id}/{file_name:path}")
async def serve_image(doc_id: str, file_name: str):
    """提供上传目录中的图片文件"""
    upload_dir = os.path.join(settings.UPLOAD_DIR, doc_id)
    file_path = os.path.join(upload_dir, file_name)

    # 安全检查: 确保路径在 upload_dir 内
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(upload_dir)):
        raise HTTPException(403, "禁止访问")

    if not os.path.exists(real_path):
        raise HTTPException(404, "图片不存在")

    return FileResponse(real_path)


@router.post("/image-search", response_model=ImageSearchResponse)
async def image_search(req: ImageSearchRequest, db: AsyncSession = Depends(get_db)):
    results = retriever.image_only_search(req.image_base64, req.top_k)

    doc_ids = {r["doc_id"] for r in results if r.get("doc_id")}
    doc_names: dict[str, str] = {}
    if doc_ids:
        try:
            from uuid import UUID
            uuids = [UUID(d) for d in doc_ids]
            rows = await db.execute(
                select(Document.filename, Document.id).where(Document.id.in_(uuids))
            )
            for filename, did in rows:
                doc_names[str(did)] = filename
        except ValueError:
            pass

    items = []
    for r in results:
        items.append(ImageSearchResult(
            doc_name=doc_names.get(r.get("doc_id", ""), r.get("doc_id", "")),
            doc_id=r.get("doc_id", ""),
            image_url=_to_api_url(r.get("image_path", "")),
            page=r.get("page", 1),
            score=r.get("score", 0),
        ))
    return ImageSearchResponse(results=items)

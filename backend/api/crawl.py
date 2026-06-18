"""爬取编排 API"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from backend.models.database import get_db
from backend.models.documents import Document
from backend.core.crawler import ADAPTERS, fetch_urls_async
from backend.core.tasks import process_crawled_document
from backend.core.redis_client import clear_cache

router = APIRouter()


class CrawlRequest(BaseModel):
    source: str = "gov_zhengce"
    limit: int = 20
    max_body_length: int = 200000


@router.post("/documents/crawl")
async def crawl_documents(req: CrawlRequest, db: AsyncSession = Depends(get_db)):
    """触发一次爬取任务: 发现 URL → 抓取 → 清洗 → 入库 → 向量化"""
    adapter = ADAPTERS.get(req.source)
    if not adapter:
        raise HTTPException(400, f"未知来源: {req.source}, 可用: {list(ADAPTERS.keys())}")

    urls = adapter.discover_urls(limit=req.limit)
    fetched = await fetch_urls_async(urls)

    # 批量去重: 一次查询所有已爬取的 URL
    urls_to_check = [url for url, _ in fetched]
    existing_rows = await db.execute(
        select(Document.source_url).where(Document.source_url.in_(urls_to_check))
    )
    existing_urls = {row[0] for row in existing_rows}

    results = []
    skipped = 0
    for url, html in fetched:
        if url in existing_urls:
            skipped += 1
            continue

        try:
            page = adapter.parse_page(html, url)
        except Exception:
            continue

        if not page.body_text or len(page.body_text) < 50:
            continue

        body_text = page.body_text[:req.max_body_length]

        doc_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            filename=page.title or url.rsplit("/", 1)[-1],
            file_size=len(body_text.encode("utf-8")),
            file_path="",
            status="pending",
            source_url=url,
            source_type="crawled",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        process_crawled_document.delay(
            str(doc.id), page.title or url, body_text, url
        )
        results.append({"id": str(doc.id), "title": page.title, "url": url})

    clear_cache()
    return {"crawled": len(results), "skipped": skipped, "items": results}


@router.get("/documents/crawl/sources")
async def list_crawl_sources():
    """列出可用的爬取源"""
    return {
        name: {"name": a.name, "base_url": a.base_url}
        for name, a in ADAPTERS.items()
    }

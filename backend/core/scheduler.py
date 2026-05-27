"""定时爬取调度器"""
from backend.core.celery_app import app


@app.task
def daily_crawl():
    """每天自动从所有数据源爬取最新文档（每源 10 篇）"""
    import asyncio
    import uuid
    from backend.core.crawler import ADAPTERS, create_client, fetch_urls
    from backend.core.tasks import process_crawled_document
    from backend.models.database import async_session
    from backend.models.documents import Document

    async def _run():
        total = 0
        async with async_session() as db:
            for name, adapter in ADAPTERS.items():
                urls = adapter.discover_urls(limit=10)
                client = create_client()
                fetched = fetch_urls(client, urls)
                client.close()

                for url, html in fetched:
                    try:
                        page = adapter.parse_page(html, url)
                    except Exception:
                        continue
                    if not page.body_text or len(page.body_text) < 50:
                        continue

                    doc_id = uuid.uuid4()
                    doc = Document(
                        id=doc_id,
                        filename=page.title or url.rsplit("/", 1)[-1],
                        file_size=len(page.body_text.encode("utf-8")),
                        file_path="",
                        status="pending",
                        source_url=url,
                        source_type="crawled",
                    )
                    db.add(doc)
                    await db.commit()
                    await db.refresh(doc)
                    process_crawled_document.delay(str(doc.id), page.title or url, page.body_text, url)
                    total += 1
        return total

    count = asyncio.run(_run())
    return f"Crawled {count} documents"

import os
from backend.core.celery_app import app
from backend.core.cleaning import clean_document
from backend.core import pdf_parser, image_extractor, ocr_engine, embedder, vectorstore

from sqlalchemy import update
from backend.models.database import async_session
from backend.models.documents import Document


async def _update_doc_status(doc_id: str, **kwargs):
    async with async_session() as db:
        stmt = update(Document).where(Document.id == doc_id).values(**kwargs)
        await db.execute(stmt)
        await db.commit()


def _load_bm25_on_startup():
    """启动时从所有 done 文档加载 BM25 索引"""
    import asyncio

    async def _load():
        from backend.models.database import async_session
        from backend.models.documents import Document
        from backend.core.bm25_index import build_index
        from backend.core.pdf_parser import split_text
        from sqlalchemy import select

        all_chunks = []
        async with async_session() as db:
            rows = await db.execute(
                select(Document).where(Document.status == "done")
            )
            docs = rows.scalars().all()

        for doc in docs:
            # 爬取文档: 从 Milvus 取不到正文，跳过（下次爬取时增量加入）
            if doc.source_type == "crawled":
                continue
            fpath = doc.file_path
            if not fpath or not os.path.exists(fpath):
                continue
            try:
                ext = os.path.splitext(fpath)[1].lower()
                from backend.core.pdf_parser import parse_document
                pages = parse_document(fpath, ext)
                chunks = split_text(pages)
                for c in chunks:
                    c["doc_id"] = str(doc.id)
                all_chunks.extend(chunks)
            except Exception:
                continue

        build_index(all_chunks)

    asyncio.run(_load())


def _add_to_bm25(doc_id: str, pdf_path: str):
    """增量添加文档 chunk 到 BM25 索引（文件解析）"""
    try:
        ext = os.path.splitext(pdf_path)[1].lower()
        from backend.core.pdf_parser import parse_document, split_text
        from backend.core.bm25_index import add_chunks
        pages = parse_document(pdf_path, ext)
        chunks = split_text(pages)
        for c in chunks:
            c["doc_id"] = str(doc_id)
        add_chunks(chunks)
    except Exception:
        pass


def _add_text_to_bm25(doc_id: str, text: str):
    """增量添加文本 chunk 到 BM25 索引（纯文本，用于爬取文档）"""
    try:
        from backend.core.pdf_parser import split_text
        from backend.core.bm25_index import add_chunks
        pages = [{"page": 1, "text": text}]
        chunks = split_text(pages)
        for c in chunks:
            c["doc_id"] = str(doc_id)
        add_chunks(chunks)
    except Exception:
        pass


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, doc_id: str, pdf_path: str, doc_text: str):
    import asyncio

    async def _process():
        # 1. 清理
        await _update_doc_status(str(doc_id), status="cleaning")
        cleaned_text, report, is_dup = clean_document(doc_text)

        if is_dup:
            await _update_doc_status(str(doc_id), status="failed",
                                     error_message="文档重复（相似度 > 95%）")
            return

        report_dict = {
            "headers_removed": report.headers_removed,
            "noise_removed": report.noise_removed,
            "paragraphs_merged": report.paragraphs_merged,
            "duplicates_found": report.duplicates_found,
        }

        # 2. 解析 — 根据文件扩展名路由
        await _update_doc_status(str(doc_id), status="embedding")
        ext = os.path.splitext(pdf_path)[1].lower()
        pages = pdf_parser.parse_document(pdf_path, ext)
        chunks = pdf_parser.split_text(pages)

        # 图片文件: 上传的文件本身就是图片，直接嵌入
        img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        if ext in img_exts:
            images = [{"path": pdf_path, "page": 1}]
            for img in images:
                img["ocr_text"] = ocr_engine.ocr_image(img["path"])
        else:
            images = image_extractor.extract_images(
                pdf_path,
                os.path.join(os.path.dirname(pdf_path), "images")
            )
            for img in images:
                img["ocr_text"] = ocr_engine.ocr_image(img["path"])

        # 3. 嵌入
        await _update_doc_status(str(doc_id), status="indexing")
        if chunks:
            text_embeddings = [embedder.embed_text(c["text"]) for c in chunks]
            vectorstore.insert_texts(str(doc_id), chunks, text_embeddings)

        if images:
            image_embeddings = [embedder.embed_image(img["path"]) for img in images]
            vectorstore.insert_images(str(doc_id), images, image_embeddings)

        ocr_chunks = [{"text": img["ocr_text"], "page": img["page"], "chunk_index": -1}
                      for img in images if img.get("ocr_text", "").strip()]
        if ocr_chunks:
            ocr_embeddings = [embedder.embed_text(c["text"]) for c in ocr_chunks]
            vectorstore.insert_texts(str(doc_id), ocr_chunks, ocr_embeddings)

        # 4. 完成
        await _update_doc_status(
            str(doc_id),
            status="done",
            text_chunks=len(chunks) + len(ocr_chunks),
            image_count=len(images),
            cleaning_report=report_dict,
        )

    asyncio.run(_process())


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_crawled_document(self, doc_id: str, title: str, body_text: str, source_url: str):
    """处理网页爬取文档 — 不需要 PDF 路径"""
    import asyncio

    async def _process():
        from backend.core.html_cleaner import clean_crawled_page
        from backend.core.crawler import CrawledPage

        await _update_doc_status(str(doc_id), status="cleaning")

        page = CrawledPage(url=source_url, title=title, body_text=body_text, raw_html="")
        cleaned_text, report, is_dup = clean_crawled_page(page)

        if is_dup:
            await _update_doc_status(str(doc_id), status="failed",
                                     error_message="文档重复（相似度 > 95%）")
            return

        await _update_doc_status(str(doc_id), status="embedding")

        pages = [{"page": 1, "text": cleaned_text}]
        chunks = pdf_parser.split_text(pages)

        await _update_doc_status(str(doc_id), status="indexing")
        if chunks:
            embeddings = [embedder.embed_text(c["text"]) for c in chunks]
            vectorstore.insert_texts(str(doc_id), chunks, embeddings)

        report_dict = {
            "headers_removed": report.cleaning_report.headers_removed if report.cleaning_report else 0,
            "boilerplate_removed": report.boilterplate_removed,
            "noise_removed": report.cleaning_report.noise_removed if report.cleaning_report else 0,
            "paragraphs_merged": report.cleaning_report.paragraphs_merged if report.cleaning_report else 0,
        }

        await _update_doc_status(
            str(doc_id),
            status="done",
            text_chunks=len(chunks),
            image_count=0,
            cleaning_report=report_dict,
        )

    asyncio.run(_process())
    # 增量添加到 BM25 索引（用原始正文，避免重复解析文件）
    try:
        _add_text_to_bm25(str(doc_id), body_text)
    except Exception:
        pass


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def extract_conversation_memories(self, conversation_id: str, messages_json: str):
    """异步提取会话长期记忆 + 生成摘要"""
    import json as _json
    from backend.core.memory import extract_and_store, summarize_conversation

    messages = _json.loads(messages_json)
    extract_and_store(conversation_id, messages)
    summarize_conversation(conversation_id, messages)

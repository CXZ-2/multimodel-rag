import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.config import settings
from backend.core import pdf_parser, image_extractor, ocr_engine, embedder, vectorstore
from backend.models.schemas import UploadResponse

router = APIRouter()

MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF，触发解析和索引"""
    # 检查文件大小
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    doc_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join(settings.UPLOAD_DIR, doc_id)
    os.makedirs(upload_dir, exist_ok=True)

    # 保存 PDF
    pdf_path = os.path.join(upload_dir, file.filename)
    with open(pdf_path, "wb") as f:
        f.write(contents)

    # 1. 提取文字
    pages = pdf_parser.extract_text(pdf_path)
    chunks = pdf_parser.split_text(pages)

    # 2. 提取图片
    image_dir = os.path.join(upload_dir, "images")
    images = image_extractor.extract_images(pdf_path, image_dir)

    # 3. OCR 处理图片
    for img in images:
        ocr_text = ocr_engine.ocr_image(img["path"])
        img["ocr_text"] = ocr_text

    # 4. 文本 Embedding 并存储
    if chunks:
        text_embeddings = [embedder.embed_text(c["text"]) for c in chunks]
        vectorstore.insert_texts(doc_id, chunks, text_embeddings)

    # 5. 图片 Embedding 并存储
    if images:
        image_embeddings = [embedder.embed_image(img["path"]) for img in images]
        vectorstore.insert_images(doc_id, images, image_embeddings)

    # 6. OCR 文字也存入文本集合（使图片内容可被文本检索命中）
    ocr_chunks = []
    for img in images:
        if img.get("ocr_text", "").strip():
            ocr_chunks.append({
                "text": img["ocr_text"],
                "page": img["page"],
                "chunk_index": -1,
            })
    if ocr_chunks:
        ocr_embeddings = [embedder.embed_text(c["text"]) for c in ocr_chunks]
        vectorstore.insert_texts(doc_id, ocr_chunks, ocr_embeddings)

    return UploadResponse(
        message="PDF 上传并解析成功",
        doc_id=doc_id,
        collection_id="default",
        text_chunks=len(chunks),
        images=len(images),
    )

import re
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from backend.config import settings


# 中英文句子结束标记
_SENTENCE_END = re.compile(r"[。！？.!?\n]")


def _trim_to_sentence(text: str, min_len: int = 20) -> str:
    """修剪文本: 去掉开头标点，在最后一个完整句子处截断"""
    # 去掉开头空白和标点
    cleaned = re.sub(r"^[\s，,。、；;：:！!？?…·\.\-—]+", "", text)
    # 找到最后一个句末标点，在它之后截断（保留标点）
    matches = list(_SENTENCE_END.finditer(cleaned))
    if matches:
        end = matches[-1].end()
        if end < len(cleaned) - 3:  # 只当后面还有内容时截断
            cleaned = cleaned[:end]
    return cleaned.strip()


def _is_noise_chunk(text: str) -> bool:
    """判断是否为噪声碎片: 不含足够中文字符"""
    chinese_chars = re.findall(r"[一-鿿]", text)
    return len(chinese_chars) < 5


def extract_text(pdf_path: str) -> list[dict]:
    """提取 PDF 文字，返回按页的文本块列表"""
    doc = fitz.open(pdf_path)
    try:
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                pages.append({"page": page_num + 1, "text": text})
        return pages
    finally:
        doc.close()


def split_text(pages: list[dict]) -> list[dict]:
    """语义分块: 句子边界 + embedding 相似度检测语义断点"""
    from backend.core.embedder import embed_text
    import numpy as np

    # Step 1: 按标点切句子
    all_sentences = []
    for page in pages:
        text = page.get("text", "")
        sents = re.split(r"(?<=[。！？.!?\n])\s*", text)
        for s in sents:
            s = s.strip()
            if len(s) >= 10:
                all_sentences.append({
                    "text": s,
                    "page": page.get("page", 1),
                })

    if not all_sentences:
        return []

    # Step 2: 嵌入所有句子（Chinese-CLIP）
    try:
        embeddings = [embed_text(s["text"]) for s in all_sentences]
    except Exception:
        # 嵌入失败时退回到简单分块
        return split_text_simple(pages)

    # Step 3: 按语义相似度合并句子
    chunks = []
    current = all_sentences[0]
    current_text = current["text"]
    current_page = current["page"]

    for i in range(1, len(all_sentences)):
        sim = float(np.dot(embeddings[i - 1], embeddings[i]))
        merged = current_text + " " + all_sentences[i]["text"]

        if sim > 0.6 and len(merged) <= settings.CHUNK_SIZE:
            current_text = merged
        else:
            if len(current_text) >= 20 and not _is_noise_chunk(current_text):
                chunks.append({
                    "text": _trim_to_sentence(current_text),
                    "page": current_page,
                    "chunk_index": len(chunks),
                })
            current_text = all_sentences[i]["text"]
            current_page = all_sentences[i]["page"]

    # 最后一个 chunk
    if len(current_text) >= 20 and not _is_noise_chunk(current_text):
        chunks.append({
            "text": _trim_to_sentence(current_text),
            "page": current_page,
            "chunk_index": len(chunks),
        })

    return chunks


def split_text_simple(pages: list[dict]) -> list[dict]:
    """固定大小分块（回退方案）"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )

    chunks = []
    for page in pages:
        splits = splitter.split_text(page["text"])
        for i, text in enumerate(splits):
            trimmed = _trim_to_sentence(text)
            if trimmed and not _is_noise_chunk(trimmed):
                chunks.append({
                    "text": trimmed,
                    "page": page["page"],
                    "chunk_index": i,
                })

    return chunks


# ── 多格式文档解析器统一入口 ──

_parsers: dict[str, object] = {}


def _get_parser(ext: str):
    if ext not in _parsers:
        match ext:
            case ".pdf":
                _parsers[ext] = extract_text
            case ".docx":
                from backend.core.docx_parser import parse_docx
                _parsers[ext] = parse_docx
            case ".pptx":
                from backend.core.pptx_parser import parse_pptx
                _parsers[ext] = parse_pptx
            case ".xlsx":
                from backend.core.xlsx_parser import parse_xlsx
                _parsers[ext] = parse_xlsx
            case ".md":
                from backend.core.md_parser import parse_markdown
                _parsers[ext] = parse_markdown
            case ".html" | ".htm":
                from backend.core.md_parser import parse_html
                _parsers[ext] = parse_html
            case ".jpg" | ".jpeg" | ".png" | ".bmp" | ".webp":
                from backend.core.img_parser import parse_image
                _parsers[ext] = parse_image
            case _:
                raise ValueError(f"不支持的文件类型: {ext}")
    return _parsers[ext]


def parse_document(file_path: str, file_type: str) -> list[dict]:
    """统一入口 — 根据文件扩展名调用对应解析器，返回 pages 列表"""
    ext = file_type.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    parser = _get_parser(ext)
    return parser(file_path)

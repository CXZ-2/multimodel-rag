"""Word 文档解析器"""
from docx import Document as DocxDocument


def parse_docx(file_path: str) -> list[dict]:
    doc = DocxDocument(file_path)
    pages = []
    text_buffer = ""
    page_num = 1

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if text_buffer:
                pages.append({"page": page_num, "text": text_buffer.strip()})
                text_buffer = ""
                page_num += 1
            continue
        if len(text_buffer) + len(text) > 2000:
            pages.append({"page": page_num, "text": text_buffer.strip()})
            text_buffer = text
            page_num += 1
        else:
            text_buffer += text + "\n"

    if text_buffer:
        pages.append({"page": page_num, "text": text_buffer.strip()})

    return pages

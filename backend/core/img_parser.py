"""图片文件解析器 — OCR 识别图片文字，返回单页文本"""
import os
from backend.core import ocr_engine


def parse_image(file_path: str) -> list[dict]:
    """解析图片文件 → OCR 识别文字，返回单页文本"""
    ocr_text = ""
    try:
        ocr_text = ocr_engine.ocr_image(file_path)
    except Exception:
        pass

    return [{"page": 1, "text": ocr_text or f"[图片: {os.path.basename(file_path)}]"}]

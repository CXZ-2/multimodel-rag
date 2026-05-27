from paddleocr import PaddleOCR
from backend.config import settings

_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang=settings.OCR_LANG, show_log=False)
    return _ocr


def ocr_image(image_path: str) -> str:
    """对图片进行 OCR，返回识别文字"""
    try:
        ocr = get_ocr()
        result = ocr.ocr(image_path, cls=True)

        texts = []
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                texts.append(text)

        return "\n".join(texts)
    except Exception:
        return ""

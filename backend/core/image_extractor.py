import os
import fitz  # PyMuPDF


def extract_images(pdf_path: str, output_dir: str) -> list[dict]:
    """从 PDF 提取图片，返回图片元信息列表"""
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"]

                filename = f"page{page_num + 1}_img{img_index + 1}.{ext}"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                images.append({
                    "path": filepath,
                    "page": page_num + 1,
                    "index": img_index + 1,
                    "filename": filename,
                })
        return images
    finally:
        doc.close()

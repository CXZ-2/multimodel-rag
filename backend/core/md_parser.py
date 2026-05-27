"""Markdown / HTML 解析器"""
import re
import markdown
from bs4 import BeautifulSoup


def parse_markdown(file_path: str) -> list[dict]:
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    return _parse_common(content, is_markdown=True)


def parse_html(file_path: str) -> list[dict]:
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    return _parse_common(content, is_markdown=False)


def _parse_common(content: str, is_markdown: bool = False) -> list[dict]:
    if is_markdown:
        html = markdown.markdown(content)
    else:
        html = content

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    # 按空行或标题分节，避免切太碎
    sections = re.split(r"\n\n+|\n(?=#+\s)", text)
    pages = []
    for i, section in enumerate(sections):
        section = section.strip()
        cleaned = re.sub(r"\s+", " ", section)
        if len(cleaned) > 20:
            pages.append({"page": i + 1, "text": cleaned})

    if not pages and text.strip():
        pages.append({"page": 1, "text": text.strip()})

    return pages

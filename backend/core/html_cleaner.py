"""HTML 正文清洗器 — 在已有 cleaning.py 基础上增加 HTML 特定清洗"""
import re
from dataclasses import dataclass

from backend.core.cleaning import clean_document, CleaningReport
from backend.core.crawler import CrawledPage


@dataclass
class HtmlCleaningReport:
    boilterplate_removed: int = 0
    short_lines_removed: int = 0
    total_raw_chars: int = 0
    total_clean_chars: int = 0
    cleaning_report: CleaningReport | None = None


BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(首页|返回|顶部|上一篇|下一篇|上一页|下一页)\s*$"),
    re.compile(r"^\s*(Copyright|©|版权所有|All Rights Reserved).*$", re.IGNORECASE),
    re.compile(r"^\s*(ICP|备案号|京ICP证|沪ICP备).*$"),
    re.compile(r"^\s*(分享到|微信|微博|QQ空间|豆瓣).*$"),
    re.compile(r"^\s*(关注我们|关于我们|联系我们|友情链接|网站地图).*$"),
    re.compile(r"^\s*(扫一扫|二维码|公众号|APP下载).*$"),
    re.compile(r"^\s*\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}\s*$"),
    re.compile(r"^\s*(点击|浏览量|阅读|访问次数).*\d+\s*$"),
    re.compile(r"^\s*(来源|作者|编辑|责任编辑|发布).*[:：].*$"),
]


def remove_boilerplate(text: str) -> tuple[str, int]:
    """移除 HTML 特有的模板内容（导航/页脚/版权声明）"""
    lines = text.split("\n")
    kept = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in BOILERPLATE_PATTERNS):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def clean_crawled_page(page: CrawledPage, existing_signatures: list[set] | None = None
                       ) -> tuple[str, HtmlCleaningReport, bool]:
    """
    对爬取的网页执行完整清洗:
    1. 去除 HTML 模板内容 (导航/版权/分享等)
    2. 复用 clean_document() 做页眉页脚/噪声行/段落合并/去重

    返回: (cleaned_text, report, is_duplicate)
    """
    report = HtmlCleaningReport()
    report.total_raw_chars = len(page.body_text)

    text, removed = remove_boilerplate(page.body_text)
    report.boilterplate_removed = removed

    text, cleaning_report, is_dup = clean_document(text, existing_signatures)
    report.cleaning_report = cleaning_report
    report.total_clean_chars = len(text)

    return text, report, is_dup

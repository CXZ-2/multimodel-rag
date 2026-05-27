import re
from dataclasses import dataclass


@dataclass
class CleaningReport:
    headers_removed: int = 0
    noise_removed: int = 0
    paragraphs_merged: int = 0
    duplicates_found: int = 0


HEADER_FOOTER_PATTERNS = [
    re.compile(r'^\s*第[一二三四五六七八九十\d]+章\s.*$'),
    re.compile(r'^\s*第[一二三四五六七八九十\d]+[节页]\s.*$'),
    re.compile(r'^\s*\d+\s*$'),
    re.compile(r'^\s*\d+\s*/\s*\d+\s*$'),
    re.compile(r'©\s*\d{4}.*$'),
    re.compile(r'^https?://\S+$'),
    re.compile(r'^\s*[\[\{\(].*[\]\}\)]\s*$'),
]


def clean_headers_footers(text: str) -> tuple[str, CleaningReport]:
    report = CleaningReport()
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 3:
            report.noise_removed += 1
            continue
        if any(p.match(stripped) for p in HEADER_FOOTER_PATTERNS):
            report.headers_removed += 1
            continue
        cleaned.append(line)
    return '\n'.join(cleaned), report


def merge_paragraphs(text: str, report: CleaningReport) -> str:
    lines = text.split('\n')
    merged = []
    buffer = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                merged.append(' '.join(buffer))
                if len(buffer) > 1:
                    report.paragraphs_merged += len(buffer) - 1
                buffer = []
            merged.append('')
        elif stripped.endswith(('。', '？', '！', '.', '?', '!')):
            buffer.append(stripped)
            merged.append(' '.join(buffer))
            if len(buffer) > 1:
                report.paragraphs_merged += len(buffer) - 1
            buffer = []
        else:
            buffer.append(stripped)
    if buffer:
        merged.append(' '.join(buffer))
        if len(buffer) > 1:
            report.paragraphs_merged += len(buffer) - 1
    return '\n'.join(merged)


def compute_text_signature(text: str, n_gram: int = 5) -> set:
    words = text.lower().split()
    return {hash(' '.join(words[i:i + n_gram])) for i in range(len(words) - n_gram + 1)}


def check_duplicate(text: str, existing_signatures: list[set], threshold: float = 0.95) -> bool:
    sig = compute_text_signature(text)
    if not sig:
        return False
    for ex_sig in existing_signatures:
        overlap = len(sig & ex_sig) / max(len(sig), 1)
        if overlap >= threshold:
            return True
    return False


def clean_document(text: str, existing_signatures: list[set] | None = None) -> tuple[str, CleaningReport, bool]:
    text, report = clean_headers_footers(text)
    text = merge_paragraphs(text, report)
    is_dup = False
    if existing_signatures:
        is_dup = check_duplicate(text, existing_signatures)
        if is_dup:
            report.duplicates_found += 1
    return text, report, is_dup

"""BM25 关键词检索索引 — 内存语料 + 增量更新"""
import re
import threading
from rank_bm25 import BM25Okapi

_corpus: list[list[str]] = []
_chunks: list[dict] = []
_bm25: BM25Okapi | None = None
_lock = threading.Lock()


def _tokenize(text: str) -> list[str]:
    """中文分词: 优先 jieba，不可用时回退到 2-gram"""
    try:
        import jieba
        return [w for w in jieba.cut(text) if len(w) > 1]
    except ImportError:
        pass
    chars = re.findall(r'[一-鿿]+', text)
    words = []
    for seg in chars:
        words.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    en_words = re.findall(r'[a-zA-Z0-9]{2,}', text)
    words.extend(w.lower() for w in en_words)
    return [w for w in words if len(w) > 1]


def build_index(all_chunks: list[dict]):
    """全量重建 BM25 索引（启动时调用）"""
    global _corpus, _chunks, _bm25
    valid_chunks = []
    corpus = []
    for c in all_chunks:
        tokens = _tokenize(c.get("text", ""))
        if tokens:
            valid_chunks.append(c)
            corpus.append(tokens)
    with _lock:
        _chunks = valid_chunks
        _corpus = corpus
        _bm25 = BM25Okapi(_corpus) if _corpus else None


def add_chunks(new_chunks: list[dict]):
    """增量添加 chunk 到现有索引"""
    global _corpus, _chunks, _bm25
    valid_chunks = []
    new_tokens = []
    for c in new_chunks:
        tokens = _tokenize(c.get("text", ""))
        if tokens:
            valid_chunks.append(c)
            new_tokens.append(tokens)
    if not new_tokens:
        return
    with _lock:
        _chunks.extend(valid_chunks)
        _corpus.extend(new_tokens)
        _bm25 = BM25Okapi(_corpus)
        _bm25 = BM25Okapi(_corpus)


def remove_doc(doc_id: str):
    """按 doc_id 移除 chunk（从索引中剔除）"""
    global _corpus, _chunks, _bm25
    with _lock:
        keep_chunks = []
        keep_corpus = []
        for i, c in enumerate(_chunks):
            if c.get("doc_id") != doc_id:
                keep_chunks.append(c)
                keep_corpus.append(_corpus[i])
        _chunks = keep_chunks
        _corpus = keep_corpus
        _bm25 = BM25Okapi(_corpus) if _corpus else None


def search(query: str, top_k: int = 10) -> list[dict]:
    """BM25 搜索"""
    global _bm25, _chunks
    if _bm25 is None:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    with _lock:
        scores = _bm25.get_scores(tokens)

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results = []
    for idx, score in indexed[:top_k]:
        chunk = dict(_chunks[idx])
        chunk["bm25_score"] = float(score)
        results.append(chunk)
    return results

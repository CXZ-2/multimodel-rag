"""Cross-Encoder 语义重排序 — BGE-Reranker v2 M3，失败时回退到 2-gram"""
import os
import re

_model = None
_tried = False


def _tokenize(text: str) -> set[str]:
    """中文 2-gram 分词"""
    chars = re.findall(r'[一-鿿]+', text)
    words: set[str] = set()
    for seg in chars:
        for i in range(len(seg) - 1):
            words.add(seg[i:i+2])
        if len(seg) >= 2:
            words.add(seg)
    en_words = re.findall(r'[a-zA-Z0-9]{2,}', text)
    words.update(w.lower() for w in en_words)
    return words


def _get_model():
    global _model, _tried
    if _model is not None or _tried:
        return
    _tried = True
    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(
            "BAAI/bge-reranker-v2-m3",
            max_length=512,
            device="cpu",
        )
    except Exception:
        pass


def rerank(query: str, results: list[dict], top_k: int = 5) -> list[dict]:
    if not results:
        return results

    text_items = [r for r in results if r.get("type") != "image" and r.get("text")]
    image_items = [r for r in results if r.get("type") == "image" or not r.get("text")]

    if not text_items:
        return (image_items + results)[:top_k]

    # 尝试加载模型
    _get_model()

    if _model is None:
        # 2-gram 混合评分回退
        query_tokens = _tokenize(query)
        scored = []
        if query_tokens:
            for r in text_items:
                chunk_tokens = _tokenize(r.get("text", ""))
                if chunk_tokens:
                    overlap = len(query_tokens & chunk_tokens) / len(query_tokens)
                    hybrid = 0.6 * r.get("score", 0) + 0.4 * overlap
                else:
                    hybrid = r.get("score", 0)
                r["score"] = hybrid
                scored.append((hybrid, r))
        else:
            scored = [(r.get("score", 0), r) for r in text_items]
    else:
        # Cross-Encoder 精排
        pairs = [(query, r["text"][:512]) for r in text_items]
        scores = _model.predict(pairs, show_progress_bar=False)
        scored = []
        for i, r in enumerate(text_items):
            r["score"] = float(scores[i])
            scored.append((scores[i], r))

    for r in image_items:
        scored.append((r.get("score", 0), r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]

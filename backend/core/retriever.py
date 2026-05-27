from backend.core import embedder, vectorstore


def rrf_fusion(text_results: list[dict], image_results: list[dict], k: int = 60) -> list[dict]:
    """2 路 Reciprocal Rank Fusion（保留向后兼容）"""
    return rrf_fusion_3way(text_results, [], image_results, k=k)


def rrf_fusion_3way(vec_results: list[dict], bm25_results: list[dict],
                    img_results: list[dict], k: int = 60) -> list[dict]:
    """3 路 RRF 融合: 向量文本 + BM25 关键词 + 向量图片"""
    scores: dict[str, dict] = {}

    def add_results(results: list[dict], prefix: str):
        for rank, item in enumerate(results):
            # 用 text+page 作为去重 key（同一 chunk 出现在多路时合并 RRF 分数）
            dedup = f"{item.get('text', '')[:80]}_{item.get('page', 0)}"
            rrf = 1.0 / (k + rank + 1)
            if dedup in scores:
                scores[dedup]["rrf_score"] = scores[dedup]["rrf_score"] + rrf
            else:
                item_copy = dict(item)
                item_copy["rrf_score"] = rrf
                scores[dedup] = item_copy

    add_results(vec_results, "vec")
    add_results(bm25_results, "bm25")
    add_results(img_results, "img")

    sorted_items = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    return sorted_items


def hybrid_search(question: str, image_base64: str = None, top_k: int = 5) -> list[dict]:
    """混合检索：向量文本 + BM25 关键词 + 向量图片，三路 RRF 融合"""
    # 多路检索时扩大候选池
    pool_size = top_k * 3

    # 1. 向量文本检索
    text_embedding = embedder.embed_text(question)
    vec_results = vectorstore.search_text(text_embedding, pool_size)

    # 2. BM25 关键词检索
    from backend.core.bm25_index import search as bm25_search
    bm25_results = bm25_search(question, pool_size)

    # 标记来源
    for r in vec_results:
        r["source"] = "vector"
    for r in bm25_results:
        r["source"] = "bm25"

    # 3. 向量图片检索
    img_results = []
    if image_base64:
        from backend.core.embedder import embed_image_base64
        image_embedding = embed_image_base64(image_base64)
        img_results = vectorstore.search_image(image_embedding, top_k)

    return rrf_fusion_3way(vec_results, bm25_results, img_results)[:top_k]


def image_only_search(image_base64: str, top_k: int = 10) -> list[dict]:
    """以图搜图 — 编码图片 → 在 image_collection 中检索相似图片"""
    from backend.core.embedder import embed_image_base64
    image_embedding = embed_image_base64(image_base64)
    results = vectorstore.search_image(image_embedding, top_k)
    return results

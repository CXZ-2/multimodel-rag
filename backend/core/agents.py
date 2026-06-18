"""多Agent 系统 — 关键词快速分类 + LLM 路由降级 + Query Rewrite + Reranker + Cache + Memory"""

from backend.core.generator import _call_llm, _call_llm_stream
from backend.core import retriever
from backend.core.classifier import classify
from backend.core.reranker import rerank
from backend.core.redis_client import get_cached, set_cache
from backend.core.memory import build_memory_context

ROUTER_PROMPT = """你是一个路由器 Agent。分析用户问题, 只回复一个词:

- 如果问题涉及金融、经济、政策、法规、市场、投资、监管、证券、银行、保险、
  基金、期货、外汇、利率、汇率、货币政策、财政、税收、资本市场等专业知识，
  需要查阅资料才能准确回答 → 回复 "RAG"
- 如果是问候、自我介绍、闲聊、一般性问题 → 回复 "GENERAL"

只回复 RAG 或 GENERAL，不要回复其他内容。"""

REWRITE_PROMPT = """将用户的口语化问题改写为更精准的检索查询。规则：
1. 补充隐含的时间、主体、背景
2. 将代词替换为具体名词
3. 扩展缩写和专业术语
4. 保持原意，不添加无关信息

只输出改写后的查询，不要解释。"""

AGENT_RAG = "rag"
AGENT_GENERAL = "general"

# RAG 检索参数
RETRIEVAL_TOP_K = 20   # 粗排候选数
RERANK_TOP_K = 5       # 精排保留数


def _route(question: str) -> str:
    """关键词快速分类 → LLM 降级（不确定时）"""
    fast = classify(question)
    if fast == "rag_fast":
        return "rag"           # 多媒体问题强制走 RAG，跳过 LLM 路由
    if fast != "rag":
        return fast
    try:
        result = _call_llm(
            f"{ROUTER_PROMPT}\n\n用户问题：{question}\n\n分类："
        )
        return "rag" if "RAG" in result.upper() else "general"
    except Exception:
        return "rag"


def _rewrite_query(question: str, history: list[dict] = None) -> str:
    """对 RAG 问题做查询改写，短问题/问候跳过，有历史时注入上下文"""
    if len(question) < 8:
        return question
    try:
        ctx = ""
        if history:
            recent = history[-4:]
            ctx = "对话历史:\n" + "\n".join(
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content'][:100]}"
                for h in recent
            ) + "\n\n"
        rewritten = _call_llm(
            f"{REWRITE_PROMPT}\n\n{ctx}原始问题：{question}\n\n改写后："
        )
        return rewritten.strip() or question
    except Exception:
        return question


def _build_general_prompt(question: str, memory_ctx: str) -> str:
    if memory_ctx:
        return f"你是一个金融助手，参考以下记忆上下文:\n{memory_ctx}\n\n请回答：{question}"
    return f"你是一个金融助手，请简洁专业地回答：{question}"


def _extract_video_info(history: list[dict] | None) -> str:
    """从对话历史中提取最近的视频上传信息"""
    if not history:
        return ""
    video_info = []
    for h in history[-6:]:
        content = h.get("content", "")
        if "视频" in content and ("处理完成" in content or "上传" in content):
            video_info.append(content[:300])
    return "\n".join(video_info) if video_info else ""


def _build_rag_prompt(question: str, results: list[dict], memory_ctx: str,
                      history: list[dict] = None) -> str:
    """构建 RAG prompt: 记忆上下文 + 视频上下文 + 参考资料 + 用户问题"""
    video_ctx = _extract_video_info(history)

    if results:
        context_text = ""
        for i, r in enumerate(results):
            text = r.get("text", "")[:300]
            doc = r.get("doc_id", "")
            page = r.get("page", 1)
            context_text += f"[来源{i+1}]({doc} 第{page}页): {text}\n\n"
        if video_ctx:
            context_text = f"[对话中的视频信息]\n{video_ctx}\n\n参考资料:\n{context_text}"
        if memory_ctx:
            context_text = f"[记忆上下文]\n{memory_ctx}\n\n{context_text}"
        return f"基于参考资料回答，标注来源编号：\n\n{context_text}\n\n用户问题：{question}"
    else:
        if video_ctx:
            prompt = f"[对话中的视频信息]\n{video_ctx}\n\n用户问题：{question}"
            if memory_ctx:
                prompt = f"[记忆上下文]\n{memory_ctx}\n\n{prompt}"
            return prompt
        prompt = f"用户问题：{question}\n\n注意：知识库中未找到相关资料，请告知用户。"
        if memory_ctx:
            prompt = f"[记忆上下文]\n{memory_ctx}\n\n{prompt}"
        return prompt


def chat(question: str, image_base64: str = None, history: list[dict] = None,
         conversation_id: str = None) -> dict:
    """多Agent 对话入口，返回 {"answer": str, "sources": list, "agent": str}"""

    if not image_base64:
        cached = get_cached(question)
        if cached:
            cached["answer"] = f"[缓存] {cached['answer']}"
            return cached

    intent = _route(question)
    memory_ctx = build_memory_context(question, conversation_id=conversation_id)

    if intent == AGENT_GENERAL:
        prompt = _build_general_prompt(question, memory_ctx)
        answer = _call_llm(prompt, image_base64=image_base64)
        result = {"answer": f"[通用回答] {answer}", "sources": [], "agent": AGENT_GENERAL}
        if not image_base64:
            set_cache(question, result["answer"], result["sources"], result["agent"])
        return result

    # RAG: rewrite → retrieve → rerank → generate
    search_query = _rewrite_query(question, history=history)
    results = retriever.hybrid_search(question=search_query, image_base64=image_base64, top_k=RETRIEVAL_TOP_K)
    results = rerank(search_query, results, top_k=RERANK_TOP_K)

    # 过滤低分来源（分数<0.1为噪声，对视频/图片问题用更高阈值）
    min_score = 0.15 if _extract_video_info(history) else 0.1
    results = [r for r in results if r.get("score", 0) >= min_score]

    prompt = _build_rag_prompt(question, results, memory_ctx, history=history)
    answer = _call_llm(prompt, image_base64=image_base64)

    result = {"answer": f"[来自知识库] {answer}", "sources": results, "agent": AGENT_RAG}
    if not image_base64:
        set_cache(question, result["answer"], result["sources"], result["agent"])
    return result


def chat_stream(question: str, image_base64: str = None, history: list[dict] = None,
                conversation_id: str = None):
    """多Agent 流式对话 — yield SSE 事件 dict: {event, data}"""
    intent = _route(question)
    memory_ctx = build_memory_context(question, conversation_id=conversation_id)

    if intent == AGENT_GENERAL:
        yield {"event": "agent", "data": AGENT_GENERAL}
        yield {"event": "token", "data": "[通用回答] "}
        prompt = _build_general_prompt(question, memory_ctx)
        for token in _call_llm_stream(prompt, image_base64=image_base64):
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}
        return

    # RAG: rewrite → retrieve → rerank → stream generate
    search_query = _rewrite_query(question, history=history)
    results = retriever.hybrid_search(question=search_query, image_base64=image_base64, top_k=RETRIEVAL_TOP_K)
    results = rerank(search_query, results, top_k=RERANK_TOP_K)

    # 有视频上下文时，只保留相关来源
    if _extract_video_info(history):
        results = [r for r in results if r.get("score", 0) > 0.5]

    yield {"event": "agent", "data": AGENT_RAG}
    yield {"event": "sources", "data": results}
    yield {"event": "token", "data": "[来自知识库] "}

    prompt = _build_rag_prompt(question, results, memory_ctx, history=history)
    for token in _call_llm_stream(prompt, image_base64=image_base64):
        yield {"event": "token", "data": token}
    yield {"event": "done", "data": ""}

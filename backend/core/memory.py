"""短期+长期记忆 — 提取、检索、注入管线"""
from backend.core import embedder
from backend.core.vectorstore import search_memories, insert_memories
from backend.core.redis_client import (
    get_conversation_window, get_conversation_summary,
    add_conversation_turn, set_conversation_summary,
)
from backend.core.generator import _call_llm

EXTRACT_PROMPT = """从以下对话中提取用户的长期记忆（事实/偏好/知识）。只提取有意义的信息，每条一行。
格式: [类型: fact|preference|knowledge] 内容

对话:
{conversation}

提取的记忆:"""


MAX_MEMORY_CHARS = 600  # 记忆上下文最长字符数


def build_memory_context(question: str, conversation_id: str = None) -> str:
    """构建记忆上下文，注入 LLM prompt。限制总长度避免 token 浪费。"""
    parts = []

    # 短期记忆: 会话窗口
    if conversation_id:
        summary = get_conversation_summary(conversation_id)
        if summary:
            parts.append(f"[对话历史摘要] {summary}")

        window = get_conversation_window(conversation_id)
        if window:
            recent = "\n".join(
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
                for m in window[-4:]  # 最近 2 轮
            )
            parts.append(f"[最近对话]\n{recent}")

    # 长期记忆: Milvus 语义检索，仅取高分
    try:
        emb = embedder.embed_text(question)
        memories = search_memories(emb, top_k=3)
        if memories:
            relevant = [m for m in memories if m["score"] > 0.6]  # 提高阈值
            if relevant:
                lines = "\n".join(f"- {m['content'][:150]}" for m in relevant)
                parts.append(f"[用户长期记忆]\n{lines}")
    except Exception:
        pass

    result = "\n\n".join(parts) if parts else ""
    # 截断到最大长度
    if len(result) > MAX_MEMORY_CHARS:
        result = result[:MAX_MEMORY_CHARS] + "..."
    return result


def extract_and_store(conversation_id: str, messages: list[dict]):
    """LLM 提取事实 → CLIP 嵌入 → 写入 PG + Milvus"""
    if len(messages) < 4:
        return

    conv_text = "\n".join(
        f"{m['role']}: {m['content'][:300]}" for m in messages[-20:]
    )

    # LLM 提取
    try:
        result = _call_llm(EXTRACT_PROMPT.format(conversation=conv_text))
        lines = [l.strip() for l in result.split("\n") if l.strip().startswith("[")]
    except Exception:
        return

    memories = []
    for line in lines:
        if "] " in line:
            mtype, content = line.split("] ", 1)
            mtype = mtype.lstrip("[")
            memories.append({"memory_type": mtype, "content": content})

    if not memories:
        return

    # 嵌入 + 存 Milvus
    try:
        embeddings = [embedder.embed_text(m["content"]) for m in memories]
        insert_memories(memories, embeddings)
    except Exception:
        pass

    # 存 PostgreSQL
    try:
        import uuid as _uuid
        import asyncio
        from backend.models.database import async_session
        from backend.models.memory import UserMemory

        async def _save():
            async with async_session() as db:
                for m in memories:
                    mem = UserMemory(
                        id=_uuid.uuid4(),
                        conversation_id=_uuid.UUID(conversation_id),
                        memory_type=m["memory_type"],
                        content=m["content"],
                    )
                    db.add(mem)
                await db.commit()

        asyncio.run(_save())
    except Exception:
        pass


def summarize_conversation(conversation_id: str, messages: list[dict]):
    """超窗口时 LLM 摘要旧轮次"""
    if len(messages) < 8:
        return

    conv_text = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in messages
    )

    try:
        summary = _call_llm(
            f"用一段话总结以下对话中用户关注的话题和重要信息：\n\n{conv_text}\n\n总结："
        )
        set_conversation_summary(conversation_id, summary.strip())
    except Exception:
        pass

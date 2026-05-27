"""Redis 客户端 — 答案缓存 + 共享连接"""
import json
import hashlib
import redis
from backend.config import settings

CACHE_DB = 1
CACHE_TTL = 3600  # 1 小时

_client = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        url = settings.REDIS_URL
        if "/0" in url:
            url = url.replace("/0", f"/{CACHE_DB}")
        _client = redis.from_url(url, decode_responses=True)
    return _client


def cache_key(question: str) -> str:
    return f"qa:{hashlib.md5(question.strip().encode()).hexdigest()}"


def get_cached(question: str) -> dict | None:
    try:
        raw = get_client().get(cache_key(question))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set_cache(question: str, answer: str, sources: list[dict], agent: str):
    try:
        get_client().setex(
            cache_key(question),
            CACHE_TTL,
            json.dumps({
                "answer": answer,
                "sources": sources,
                "agent": agent,
            }, ensure_ascii=False),
        )
    except Exception:
        pass


def clear_cache():
    try:
        get_client().flushdb()
    except Exception:
        pass


# ── 短期记忆（会话窗口 + 摘要）──
SHORT_MEMORY_TTL = 86400  # 24 小时


def add_conversation_turn(conversation_id: str, role: str, content: str):
    """追加一轮对话到 Redis 列表，保留最近 10 条"""
    try:
        r = get_client()
        key = f"conv:{conversation_id}"
        r.rpush(key, json.dumps({"role": role, "content": content[:500]}, ensure_ascii=False))
        r.ltrim(key, -10, -1)
        r.expire(key, SHORT_MEMORY_TTL)
    except Exception:
        pass


def get_conversation_window(conversation_id: str) -> list[dict]:
    """获取会话窗口中的最近对话"""
    try:
        raw = get_client().lrange(f"conv:{conversation_id}", 0, -1)
        return [json.loads(r) for r in raw] if raw else []
    except Exception:
        return []


def get_conversation_summary(conversation_id: str) -> str | None:
    """获取 LLM 生成的会话摘要"""
    try:
        return get_client().get(f"conv_summary:{conversation_id}")
    except Exception:
        return None


def set_conversation_summary(conversation_id: str, summary: str):
    """设置会话摘要"""
    try:
        get_client().setex(f"conv_summary:{conversation_id}", SHORT_MEMORY_TTL, summary)
    except Exception:
        pass

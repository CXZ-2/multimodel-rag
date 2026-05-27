"""健康检查端点"""
from fastapi import APIRouter
from sqlalchemy import text

from backend.models.database import async_session

router = APIRouter()


@router.get("/health")
async def health():
    """检查各组件连通性"""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Milvus — use separate alias to avoid disconnecting the app connection
    try:
        from pymilvus import connections
        connections.connect("health_check", host="milvus-standalone", port=19530, timeout=5)
        connections.disconnect("health_check")
        checks["milvus"] = "ok"
    except Exception as e:
        checks["milvus"] = f"error: {e}"

    # Redis
    try:
        import redis
        r = redis.Redis(host="redis", port=6379, socket_connect_timeout=3)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}

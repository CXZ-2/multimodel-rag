"""结构化日志 — 请求 ID + 耗时记录 (纯 ASGI 中间件)"""
import logging
import time
import uuid

logger = logging.getLogger("rag")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger.handlers = [handler]


class RequestLoggingMiddleware:
    """纯 ASGI 中间件 — 避免 BaseHTTPMiddleware 的 greenlet 兼容问题"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message = dict(message, headers=headers)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed = time.perf_counter() - start
            method = scope.get("method", "")
            path = scope.get("path", "")
            logger.info("[%s] %s %s -> %d (%.3fs)", rid, method, path, status_code, elapsed)


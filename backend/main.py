from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import upload, query, collection, documents, conversations, crawl, health, image_search, videos
from backend.core import vectorstore
from backend.core.logging import RequestLoggingMiddleware, logger
from backend.models.database import init_db

app = FastAPI(title="OmniMind 多模态智能知识平台", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (pure ASGI, avoids greenlet issues)
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(collection.router, prefix="/api", tags=["collection"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(crawl.router, prefix="/api", tags=["crawl"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(image_search.router, prefix="/api", tags=["image-search"])
app.include_router(videos.router, prefix="/api", tags=["videos"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("[%s] %s — %s: %s", request.method, request.url.path,
                  type(exc).__name__, str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "error": str(exc)},
    )


@app.on_event("startup")
async def startup():
    vectorstore.create_collections()
    await init_db()
    # 启动时初始化 BM25 索引
    try:
        from backend.core.tasks import _load_bm25_on_startup
        _load_bm25_on_startup()
    except Exception:
        pass


@app.get("/")
def root():
    return {"message": "多模态 RAG 系统 API"}

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

多模态 RAG（检索增强生成）平台 — PDF/多格式文档上传后图文混合检索问答 + 网页爬取知识库。前端 React + Ant Design + TypeScript + Vite，后端 FastAPI + Celery + Milvus + PostgreSQL。

## 启动方式

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY
docker compose up -d --build
```

前端: `http://localhost:3000` | 后端: `http://localhost:8000` | API 文档: `http://localhost:8000/docs`

## 服务架构 (Docker Compose)

| 服务 | 端口 | 用途 |
|------|------|------|
| backend | 8000 | FastAPI (uvicorn) |
| frontend | 3000 | React SPA (nginx 反向代理 /api → backend) |
| postgres | 5432 | 文档/对话数据 (pgvector) |
| milvus-standalone | 19530 | 向量检索 (text_collection + image_collection) |
| redis | 6379 | Celery 消息队列 |
| celery-worker | — | 异步文档处理 (解析→清洗→嵌入→索引) |
| celery-beat | — | 定时爬取调度 |
| minio | 9000 | Milvus 对象存储 |
| etcd | 2379 | Milvus 元数据 |

## 后端架构

```
backend/
  main.py              # FastAPI 入口，注册所有路由 + 全局异常处理 + 纯ASGI日志中间件
  config.py            # pydantic-settings，环境变量从 .env 读取
  api/
    query.py           # POST /api/query — 多Agent问答 (classifier路由 → general/rag)
    upload.py          # POST /api/upload
    documents.py       # 文档CRUD: upload/list/get/delete/batch-delete
    crawl.py           # POST /api/documents/crawl + GET sources
    conversations.py   # 对话CRUD
    image_search.py    # POST /api/image-search — 以图搜图 (计划中)
    collection.py      # Milvus 集合管理
    health.py          # GET /api/health — 检查 postgres/milvus/redis
  core/
    agents.py          # 多Agent: Router(LLM) → General Agent / RAG Agent (零额外依赖)
    classifier.py      # 关键词意图分类器 (rag vs general)
    retriever.py       # hybrid_search: 文本+图片混合检索 + RRF融合
    generator.py       # 通义千问: generate_answer (RAG) / generate_general_answer (通用)
    embedder.py        # Chinese-CLIP: embed_text / embed_image
    vectorstore.py     # Milvus: create_collections / search_text / search_image
    pdf_parser.py      # PDF解析 + 分块 + 多格式统一入口 parse_document()
    docx_parser.py     # Word解析 (计划中)
    pptx_parser.py     # PPT解析 (计划中)
    xlsx_parser.py     # Excel解析 (计划中)
    md_parser.py       # Markdown/HTML解析 (计划中)
    ocr_engine.py      # PaddleOCR 中文识别
    image_extractor.py # PyMuPDF 提取PDF内嵌图片
    cleaning.py        # 文本清洗 (去页眉页脚/噪声行/段落合并/去重)
    crawler.py         # 网页爬虫 + 3个站点适配器 (gov_zhengce/csrc/baidu_baike)
    html_cleaner.py    # HTML→正文 清洗
    tasks.py           # Celery任务: process_document / process_crawled_document
    scheduler.py       # Celery Beat: daily_crawl
    celery_app.py      # Celery配置
    logging.py         # RequestLoggingMiddleware (纯ASGI，非BaseHTTPMiddleware)
  models/
    database.py        # SQLAlchemy async engine + get_db() 依赖注入 (NullPool)
    documents.py       # Document 模型
    conversations.py   # Conversation + Message 模型
    schemas.py         # Pydantic 请求/响应模型
    cleaning_rules.py  # 清洗规则
```

## 数据流

### 文档入库
上传文件 → 按扩展名路由解析器 (PDF/docx/pptx/xlsx/md/html) → 提取文字(pages) → split_text 分块(在句号/换行处截断) → 去开头标点 + 过滤<5中文字符的噪声 → Chinese-CLIP编码 → 存入Milvus text_collection
                   → 同时提取图片 → PaddleOCR识别 → Chinese-CLIP编码 → 存入Milvus image_collection

### 查询
用户问题 → Router Agent (LLM判断意图):
  → "general": General Agent → 通义千问直接回答 [通用回答]
  → "rag":    RAG Agent → Chinese-CLIP编码问题 → text_collection + image_collection 向量检索 → RRF融合排序 → 通义千问基于上下文生成 [来自知识库]

## 关键注意事项

- **Milvus 连接别名**: 健康检查等辅助连接必须使用独立 alias (如 `health_check`)，绝不能 disconnect `"default"` 连接（会断开应用的主连接）
- **SQLAlchemy async**: 使用 NullPool 避免连接池溢出；加载关系时必须用 `selectinload()` 预加载，否则 `MissingGreenlet` 错误（async lazy load 不可用）
- **日志中间件**: 必须使用纯 ASGI 中间件，不能使用 `BaseHTTPMiddleware`（内部 `anyio.create_task_group()` 会导致 greenlet 上下文丢失）
- **前端缓存**: nginx 配置了 HTML `no-cache` + JS/CSS `immutable`。修改前端后用户需 `Ctrl+Shift+R` 硬刷新
- **Docker 重建**: 后端代码无 volume 挂载，每次修改后必须 `docker compose build backend && docker compose up -d backend`
- **`.env` 在 .gitignore 中**，永远不能提交；`.env.example` 是模板

## 测试

```bash
# 全栈服务必须运行
docker compose up -d

# 运行 E2E 测试
python3 tests/test_knowledge_base.py
```

## 环境变量 (backend/config.py)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DASHSCOPE_API_KEY | (必需) | 通义千问 API 密钥 |
| DASHSCOPE_MODEL | qwen-turbo | LLM 模型 |
| MILVUS_HOST/PORT | localhost/19530 | 向量数据库 |
| CLIP_MODEL_NAME | chinese-clip-vit-base-patch16 | 多模态嵌入模型 |
| CHUNK_SIZE/OVERLAP | 500/50 | 文本分块参数 |
| TOP_K | 5 | 检索返回数 |
| OCR_LANG | ch | PaddleOCR 语言 |
| MAX_UPLOAD_SIZE_MB | 500 | 上传限制 |

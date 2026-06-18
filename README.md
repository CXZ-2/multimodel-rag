# OmniMind 多模态智能知识平台

基于 RAG 的多模态知识库问答平台，支持 PDF/文档上传、图文混合检索、视频理解与生成、网页爬取知识库。前端 React + Ant Design + Vite，后端 FastAPI + Celery + Milvus + PostgreSQL。

## 快速启动

```bash
cp .env.example .env   # 填入 DASHSCOPE_API_KEY
docker compose up -d --build
```

- 前端: http://localhost:3000
- 后端 API 文档: http://localhost:8000/docs

## 核心功能

| 功能 | 说明 |
|------|------|
| 文档问答 | PDF/Word/PPT/Excel 上传 → 自动解析 → 图文混合检索问答 |
| 视频理解 | 上传视频 → DashScope Qwen-VL 分析 → 语音转文字 → 可检索视频内容 |
| 视频生成 | T2V 文生视频，DashScope 万相通道，支持 16:9/9:16/1:1 |
| 网页爬取 | 定时爬取政策法规网站，自动入库 |
| 以图搜图 | Chinese-CLIP 图像向量检索 |
| 对话记忆 | 短期记忆 + 长期记忆提取，多轮对话上下文 |

## 服务架构 (Docker Compose)

| 服务 | 端口 | 用途 |
|------|------|------|
| frontend | 3000 | React SPA (nginx → /api) |
| backend | 8000 | FastAPI (uvicorn) |
| postgres | 5432 | 文档/对话数据 (pgvector) |
| milvus-standalone | 19530 | 向量检索 |
| redis | 6379 | Celery 消息队列 + 缓存 |
| celery-worker | — | 异步文档/视频处理 |
| celery-beat | — | 定时爬取调度 |
| minio | 9000 | Milvus 对象存储 |
| etcd | 2379 | Milvus 元数据 |

## 技术栈

**后端:** FastAPI + Celery + SQLAlchemy + Pydantic
**深度学习:** Chinese-CLIP (嵌入) + PaddleOCR (文字识别) + faster-whisper (语音) + BGE-Reranker
**向量库:** Milvus v2.4.0 (text_collection + image_collection)
**LLM:** 通义千问 (DashScope API / OpenAI 兼容模式)
**视频:** PyAV + FFmpeg + DashScope Qwen-VL + 通义万相 T2V
**前端:** React 18 + TypeScript + Ant Design + Vite + ReactMarkdown

## 环境变量

| 变量 | 说明 |
|------|------|
| DASHSCOPE_API_KEY | 通义千问 API 密钥 (必需) |
| DASHSCOPE_MODEL | LLM 模型 (默认 qwen-turbo) |
| DASHSCOPE_VL_MODEL | 视觉模型 (默认 qwen-vl-plus) |
| MILVUS_HOST/PORT | Milvus 连接 |
| MAX_UPLOAD_SIZE_MB | 文件上传上限 (默认 500MB) |

## 项目结构

```
backend/
  main.py           # FastAPI 入口
  config.py         # pydantic-settings 配置
  api/              # REST API (query, documents, videos, conversations, crawl)
  core/             # 核心模块 (agents, retriever, embedder, generator, video_*)
  models/           # SQLAlchemy 模型 + Pydantic schemas

frontend/
  src/
    pages/          # 页面组件 (Chat, Upload, KnowledgeBase, ImageSearch)
    services/       # API 调用层 (axios + SSE)
    components/     # 共享组件 (Sidebar)
```

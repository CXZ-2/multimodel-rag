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
| 智能问答 | 多 Agent 路由 (LLM 意图分类 → General/RAG)，图文混合检索 + RRF 融合排序 |
| 文档问答 | PDF/Word/PPT/Excel/Markdown 上传 → 自动解析分块 → 图文混合检索问答 |
| 视频理解 | 上传视频 → DashScope Qwen-VL 原生视频理解 + faster-whisper 语音转文字 → 关键帧 CLIP 嵌入 → 可检索视频内容 |
| 视频生成 | T2V 文生视频，DashScope 万相通道，支持 720P/1080P、16:9/9:16/1:1、2-15 秒 |
| 网页爬取 | 定时爬取政策法规网站 (gov.cn/csrc/baidu_baike)，自动清洗入库 |
| 以图搜图 | Chinese-CLIP 图像向量检索，支持上传图片搜索相似内容 |
| 对话记忆 | 多轮对话上下文 + 会话持久化，视频上传/生成自动入库到对话 |

## 服务架构 (Docker Compose)

| 服务 | 端口 | 用途 |
|------|------|------|
| frontend | 3000 | React SPA (nginx 反向代理 /api → backend) |
| backend | 8000 | FastAPI (uvicorn) |
| postgres | 5432 | 文档/对话数据 (pgvector) |
| milvus-standalone | 19530 | 向量检索 (text_collection + image_collection) |
| redis | 6379 | Celery 消息队列 + 缓存 |
| celery-worker | — | 异步文档/视频处理 |
| celery-beat | — | 定时爬取调度 |
| minio | 9000 | Milvus 对象存储 |
| etcd | 2379 | Milvus 元数据 |

## 技术栈

**后端:** FastAPI + Celery + SQLAlchemy 2.0 (async) + Pydantic v2
**深度学习:** Chinese-CLIP (文本+图像嵌入) + PaddleOCR (文字识别) + faster-whisper (语音转文字) + BGE-Reranker (重排序)
**向量库:** Milvus v2.4.0 (text_collection + image_collection)
**LLM:** 通义千问 (DashScope API / OpenAI 兼容模式)
**视频:** PyAV (关键帧提取) + FFmpeg (音频提取) + DashScope Qwen-VL (视频理解) + 通义万相 (T2V 生成)
**前端:** React 18 + TypeScript + Ant Design 5 + Vite + ReactMarkdown

## 环境变量

| 变量 | 说明 |
|------|------|
| DASHSCOPE_API_KEY | 通义千问 API 密钥 (必需) |
| DASHSCOPE_MODEL | LLM 模型 (默认 qwen-turbo) |
| DASHSCOPE_VL_MODEL | 视觉模型 (默认 qwen-vl-max) |
| VIDEO_UNDERSTAND_MODEL | 视频理解模型 (默认 qwen-vl-max) |
| T2V_MODEL | 文生视频模型 (默认 wanx2.1-t2v-turbo) |
| MILVUS_HOST/PORT | Milvus 连接 |
| MAX_UPLOAD_SIZE_MB | 文件上传上限 (默认 500MB) |
| MAX_VIDEO_SIZE_MB | 视频上传上限 (默认 500MB) |

## 项目结构

```
backend/
  main.py              # FastAPI 入口，注册所有路由 + 全局异常处理
  config.py            # pydantic-settings，环境变量从 .env 读取
  api/
    query.py           # POST /api/query — 多Agent问答
    upload.py          # POST /api/upload — 文件上传
    documents.py       # 文档 CRUD
    videos.py          # 视频上传/状态/列表/删除 + T2V 生成 + 代理播放
    conversations.py   # 对话 CRUD + 消息追加
    crawl.py           # 网页爬取
    image_search.py    # 以图搜图
    collection.py      # Milvus 集合管理
    health.py          # 健康检查
  core/
    agents.py          # 多Agent路由 (Router → General/RAG)
    classifier.py      # 关键词意图分类 (含视频媒体关键词)
    retriever.py       # 混合检索 (文本+图片) + RRF 融合
    generator.py       # 通义千问 LLM 调用
    embedder.py        # Chinese-CLIP 文本/图像嵌入
    vectorstore.py     # Milvus 向量存储操作
    video_parser.py    # PyAV 关键帧提取 + FFmpeg 音频提取
    video_understander.py  # DashScope Qwen-VL 视频理解 + faster-whisper 语音识别
    video_generator.py     # T2V 多通道生成 (万相/Sora)
    pdf_parser.py      # PDF 解析 + 分块 + 多格式统一入口
    docx_parser.py     # Word 解析
    pptx_parser.py     # PPT 解析
    xlsx_parser.py     # Excel 解析
    md_parser.py       # Markdown/HTML 解析
    ocr_engine.py      # PaddleOCR 中文识别
    image_extractor.py # PyMuPDF 提取 PDF 内嵌图片
    cleaning.py        # 文本清洗
    crawler.py         # 网页爬虫 + 站点适配器
    html_cleaner.py    # HTML → 正文清洗
    tasks.py           # Celery 任务 (文档处理 + 视频处理)
    scheduler.py       # Celery Beat 定时调度
    celery_app.py      # Celery 配置
    logging.py         # 请求日志中间件
  models/
    database.py        # SQLAlchemy async engine
    documents.py       # Document 模型
    conversations.py   # Conversation + Message 模型
    schemas.py         # Pydantic 请求/响应模型

frontend/
  src/
    pages/
      Chat.tsx         # 智能问答 (含视频上传+生成集成)
      Upload.tsx       # 文档上传
      KnowledgeBase.tsx # 知识库管理
      ImageSearch.tsx  # 以图搜图
    services/
      api.ts           # API 调用层 (axios + SSE)
    components/
      Sidebar.tsx      # 侧边栏导航
```

## 视频处理流水线

```
上传视频 → Celery 异步处理:
  1. PyAV 提取元数据 (时长/分辨率/帧率)
  2. FFmpeg 提取音频 → faster-whisper 语音转文字
  3. DashScope Qwen-VL 视频理解 → 结构化 JSON (摘要/场景/事件/物体/OCR/风格/标签)
  4. PyAV 提取关键帧 → Chinese-CLIP 嵌入 → Milvus image_collection
  5. 摘要+转录文本分块 → Chinese-CLIP 嵌入 → Milvus text_collection
  6. 更新 Document 状态为 done, 存入理解报告

视频问答 → 分类器检测媒体关键词 → 强制走 RAG → 从对话历史提取视频上下文 → 检索过滤低分来源
```

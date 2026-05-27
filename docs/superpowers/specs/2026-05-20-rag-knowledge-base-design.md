# RAG 平台知识库管理 — 设计文档

**日期**: 2026-05-20
**方案**: B — PostgreSQL 业务数据库 + Milvus 向量检索分离

---

## 一、数据模型

新增 PostgreSQL 数据库 `rag_platform`，以下 4 张表：

### documents（文档表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 文档唯一 ID |
| filename | VARCHAR(512) | 原始文件名 |
| file_size | BIGINT | 文件大小(字节) |
| file_path | VARCHAR(1024) | 容器内存储路径 |
| status | VARCHAR(32) | pending/cleaning/embedding/indexing/done/failed |
| text_chunks | INT | 文本块数 |
| image_count | INT | 提取的图片数 |
| cleaning_report | JSONB | 清理报告(去脏数/合并段落数/去重数) |
| error_message | TEXT | 失败原因 |
| uploaded_at | TIMESTAMP | 上传时间 |
| updated_at | TIMESTAMP | 最后更新时间 |

### conversations（会话表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 会话 ID |
| title | VARCHAR(256) | 会话标题(自动生成) |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 最后消息时间 |

### messages（消息表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 消息 ID |
| conversation_id | UUID FK | 所属会话 |
| role | VARCHAR(16) | user / assistant |
| content | TEXT | 消息内容 |
| image_base64 | TEXT | 用户发图片时的 base64 |
| sources | JSONB | 引用来源(doc_id/page/score) |
| created_at | TIMESTAMP | 创建时间 |

### cleaning_rules（清理规则表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 规则 ID |
| name | VARCHAR(128) | 规则名称 |
| rule_type | VARCHAR(32) | header_footer/noise/merge_dedup |
| enabled | BOOLEAN | 是否启用 |
| config | JSONB | 规则参数 |

---

## 二、API 设计

### 文档管理

- `POST /api/documents/upload` — 批量上传(接受多个 PDF)
- `GET /api/documents` — 列表(分页、状态筛选)
- `GET /api/documents/{id}` — 详情 + 文本内容预览
- `DELETE /api/documents/{id}` — 删除文档(Milvus + 磁盘 + 数据库同步清除)
- `GET /api/documents/{id}/status` — 查询解析进度(用于轮询进度条)

### 对话管理

- `GET /api/conversations` — 历史会话列表
- `POST /api/conversations` — 新建会话
- `GET /api/conversations/{id}` — 获取会话所有消息
- `DELETE /api/conversations/{id}` — 删除会话

### 现有 API 改动

- `POST /api/upload` — 废弃，改为调用 `POST /api/documents/upload`
- `POST /api/query` — 增加 `conversation_id` 参数，自动保存消息到 PostgreSQL

---

## 三、处理管线（Celery 异步任务）

```
用户拖拽多个 PDF → POST /api/documents/upload
  → 写入 documents 表(status=pending)，文件存磁盘
  → 提交 Celery 任务链：
      1. clean() — 去水印/页眉页脚 → 段落合并 → 文档去重
      2. parse() — PyMuPDF 提取文字 + 图片 + OCR
      3. embed() — Chinese-CLIP 编码 → Milvus 写入
      4. done()  — 更新 status=done，写 cleaning_report
  → 前端轮询 GET /api/documents/{id}/status 更新进度条
```

### 进度状态机

```
pending → cleaning → embedding → indexing → done
                                          ↘ failed
```

---

## 四、数据清理规则

1. **去水印/页眉页脚**: 正则匹配重复出现的模式行(如 "第X页"、"©2024"、网址等)，在分块前从原始文本中剔除
2. **段落合并**: 检测被错误拆分的段落(以句号/问号结尾的行不应拆分)，合并相邻文本块
3. **文档去重**: 对每个文档的文本计算 MinHash 指纹，与新文档比对，相似度 > 95% 标记为重复，阻止索引

---

## 五、前端改动

### 知识库管理页（新增，侧边栏导航）

- 文档列表(表格): 复选框、文件名、大小、状态标签、文本块数、上传时间
- 批量操作栏: 批量删除、搜索过滤、状态筛选
- 点击文件名 → 右侧滑出详情面板:
  - 文件信息 + 下载/删除按钮
  - 清理报告概要
  - 文本内容预览（分页显示）

### 批量上传

- 拖拽区域支持多文件 + 点击多选
- 上传队列面板: 每文件独立进度条，整体进度(X/N)
- 完成自动刷新文档列表

### 对话页面

- 左侧: 历史会话列表(从 PostgreSQL 加载)
- 右侧: 当前对话消息
- 新建/切换/删除会话

---

## 六、技术依赖

| 组件 | 选型 |
|---|---|
| 业务数据库 | PostgreSQL 16 + pgvector 扩展 |
| 异步任务队列 | Celery + Redis broker |
| ORM | SQLAlchemy 2.0 + asyncpg |
| 文件存储 | 本地磁盘 + Docker volume `uploads` |
| 迁移工具 | Alembic |

---

## 七、验证方式

1. `docker compose up -d` — 所有服务(含 PostgreSQL)正常启动
2. `POST /api/documents/upload` 上传 3 个 PDF，200 OK
3. Celery worker 日志显示 清理→解析→嵌入→完成 管线
4. `GET /api/documents` 返回文档列表，包含状态和清理报告
5. 前端知识库页面可查看文档列表、点击查看内容
6. 对话页面可创建会话、发送问题，消息保存到 PostgreSQL
7. 刷新对话页面后历史消息仍然存在

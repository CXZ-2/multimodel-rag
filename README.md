🚀 OmniMind - 多模态智能知识平台
## 系统演示
<img width="1904" height="910" alt="image" src="https://github.com/user-attachments/assets/bd3697f7-2472-4fac-ab0d-2b7d2136ec5c" />

<img width="1900" height="915" alt="image" src="https://github.com/user-attachments/assets/7d6e0e31-ab67-40f6-a3b5-f1e3de2885e3" />

<img width="1340" height="643" alt="image" src="https://github.com/user-attachments/assets/490e3a6f-c950-43ef-b032-5ebe90444dea" />

<img width="1340" height="642" alt="image" src="https://github.com/user-attachments/assets/73226508-7d6b-4eea-8b1a-e1e4f0fab582" />


<div align="center">
基于 RAG + CLIP + LLM 的企业级多模态知识库系统

支持 PDF、图片、文本统一检索与智能问答

</div>

📖 项目简介

OmniMind 是一个基于 Retrieval-Augmented Generation（RAG） 构建的多模态智能知识平台。

系统能够同时理解：

📄 文本文档
🖼 图片内容
📑 PDF文件
🧠 企业知识库

通过结合：

大语言模型（LLM）
CLIP视觉模型
向量数据库
检索增强生成（RAG）

实现企业级知识管理与智能问答能力。

✨ 核心功能
📚 智能知识库
文档上传
文档解析
自动切分 Chunk
向量化存储
知识检索
🔍 多模态检索

支持：

文本 → 文本检索
文本 → 图片检索
图片 → 图片检索
图片 → 文本检索

基于 CLIP 实现跨模态语义理解。

🤖 智能问答

用户提问：

请解释系统架构图中的核心组件

系统流程：

问题
 ↓
向量检索
 ↓
相关文档
 ↓
LLM推理
 ↓
最终答案


🖼 图文联合理解

支持：

PDF图片抽取
图文关联
图像语义搜索
图表内容分析
⚡ Docker 一键部署

项目内置：

docker-compose.yml

支持快速启动整套服务。

🏗 系统架构


                  ┌────────────────┐
                  │    用户提问     |
                  └────────┬───────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │      API服务      │
                  └────────┬─────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼

    文本检索模块          图像检索模块       多模态检索模块

        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼

                 向量数据库(Vector DB)

                           │
                           ▼

                    大语言模型(LLM)

                           │
                           ▼

                        最终答案

                        
📂 项目结构

OmniMind
│
├── backend/                 # 后端服务
│
├── frontend/                # 前端项目
│
├── tests/                   # 测试代码
│
├── docs/
│   └── superpowers/specs/   # 项目设计文档
│
├── .env.example             # 环境变量示例
│
├── docker-compose.yml       # Docker部署
│
└── README.md

⚙️ 环境要求

推荐配置：

项目	版本
Python	3.10+
Node.js	18+
Docker	Latest
CUDA	11.8+（可选）


🚀 快速开始

1. 克隆项目
git clone https://github.com/CXZ-2/multimodel-rag.git

cd multimodel-rag

2. 配置环境变量

复制配置文件：

cp .env.example .env

填写：

OPENAI_API_KEY=your_api_key

MODEL_NAME=gpt-4o

EMBEDDING_MODEL=clip

3. Docker启动
docker-compose up -d

查看运行状态：

docker ps

💻 本地开发

Backend
cd backend

pip install -r requirements.txt

python main.py
Frontend
cd frontend

npm install

npm run dev

📸 使用流程
上传文档
      ↓
自动解析
      ↓
向量化存储
      ↓
构建知识库
      ↓
用户提问
      ↓
多模态检索
      ↓
LLM生成答案

🎯 应用场景
企业知识库
制度文档查询
产品手册问答
内部知识管理
AI助手
智能客服
企业Copilot
私有化GPT
学术研究
论文问答
图表检索
文献分析
多模态搜索
图片搜索
图文检索
PDF理解

🛠 技术栈

后端
FastAPI
LangChain
LlamaIndex
CLIP
OpenAI API

前端
Vue3
Vite
TypeScript
AI能力
RAG
CLIP Embedding
Multimodal Search
LLM Reasoning

部署
Docker
Docker Compose

📈 Roadmap
 多模态检索
 PDF解析
 CLIP集成
 Docker部署
 Milvus支持
 Qdrant支持
 用户权限管理
 知识库共享
 MCP支持
 Agent工作流
 
🤝 贡献指南

欢迎提交：

Bug修复
功能增强
文档优化
性能优化

提交流程：

Fork
 ↓
Create Branch
 ↓
Commit
 ↓
Push
 ↓
Pull Request
⭐ Star History

如果这个项目对你有帮助，欢迎点一个 Star ⭐

你的支持是项目持续更新的动力。

📄 License

Apache License 2.0

👨‍💻 作者

CXZ-2

GitHub：

https://github.com/CXZ-2

欢迎交流 RAG、Agent、多模态 AI 与企业级知识库系统。

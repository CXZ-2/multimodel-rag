from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # PostgreSQL + Redis
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag123@localhost:5432/rag_platform"
    REDIS_URL: str = "redis://localhost:6379/0"

    # DashScope (通义千问)
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-turbo-latest"
    DASHSCOPE_VL_MODEL: str = "qwen-vl-plus"      # 多模态视觉模型

    # Chinese-CLIP
    CLIP_MODEL_NAME: str = "OFA-Sys/chinese-clip-vit-base-patch16"

    # PaddleOCR
    OCR_LANG: str = "ch"

    # 应用
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 500
    # 视频处理
    MAX_VIDEO_SIZE_MB: int = 500
    VIDEO_FPS: float = 2.0             # DashScope 视频理解抽帧频率
    VIDEO_KEY_FRAMES: int = 10         # 提取关键帧数量
    VIDEO_UNDERSTAND_MODEL: str = "qwen-vl-max"  # 视频理解模型
    T2V_MODEL: str = "wanx2.1-t2v-turbo"         # 默认文生视频模型
    FRAMES_DIR: str = "uploads/frames" # 关键帧存储目录
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    class Config:
        env_file = ".env"


settings = Settings()

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    image_base64: Optional[str] = None
    collection_id: str = "default"
    top_k: int = 5


class SourceItem(BaseModel):
    type: str  # "text" or "image"
    index: int  # 来源编号，对应 LLM 回答中的 [来源N]
    content: Optional[str] = None
    image_url: Optional[str] = None
    page: int
    score: float  # 余弦相似度 0-1
    doc_name: str = ""  # 所属文档名


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class UploadResponse(BaseModel):
    message: str
    doc_id: str
    collection_id: str
    text_chunks: int
    images: int


class CollectionInfo(BaseModel):
    id: str
    name: str
    doc_count: int
    created_at: str


# --- 文档管理 ---

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_size: int
    status: str
    text_chunks: int
    image_count: int
    cleaning_report: dict
    source_url: Optional[str] = None
    source_type: str = "uploaded"
    uploaded_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)

    class Config:
        from_attributes = True


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class DocumentStatusOut(BaseModel):
    id: str
    status: str
    text_chunks: int
    image_count: int
    error_message: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


# --- 对话管理 ---

class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    image_base64: Optional[str] = None
    sources: Optional[list] = None
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)

    class Config:
        from_attributes = True


class ConversationDetailOut(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


# --- 以图搜图 ---

class ImageSearchRequest(BaseModel):
    image_base64: str
    top_k: int = 10


class ImageSearchResult(BaseModel):
    doc_name: str
    doc_id: str = ""
    image_url: str
    page: int
    score: float


class ImageSearchResponse(BaseModel):
    results: list[ImageSearchResult]

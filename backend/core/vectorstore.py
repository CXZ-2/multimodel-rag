from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from backend.config import settings

TEXT_COLLECTION = "text_collection"
IMAGE_COLLECTION = "image_collection"
MEMORY_COLLECTION = "memory_collection"

_connected = False


def connect():
    global _connected
    if not _connected:
        connections.connect(host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        _connected = True


def create_collections(dim: int = 512):
    """创建文本和图片向量集合"""
    connect()

    # 文本集合
    if not utility.has_collection(TEXT_COLLECTION):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="page", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields)
        col = Collection(TEXT_COLLECTION, schema)
        col.create_index("embedding", {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        })

    # 图片集合
    if not utility.has_collection(IMAGE_COLLECTION):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="image_path", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="page", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields)
        col = Collection(IMAGE_COLLECTION, schema)
        col.create_index("embedding", {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        })

    # memory_collection
    if not utility.has_collection(MEMORY_COLLECTION):
        mem_fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="memory_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="memory_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        mem_schema = CollectionSchema(mem_fields)
        mem_col = Collection(MEMORY_COLLECTION, mem_schema)
        mem_col.create_index("embedding", {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        })

    # 加载集合到内存
    for name in [TEXT_COLLECTION, IMAGE_COLLECTION, MEMORY_COLLECTION]:
        if utility.has_collection(name):
            Collection(name).load()


def insert_texts(doc_id: str, chunks: list[dict], embeddings: list[list[float]]):
    """插入文本数据"""
    connect()
    col = Collection(TEXT_COLLECTION)
    data = [
        [doc_id] * len(chunks),
        [c["text"] for c in chunks],
        [c["page"] for c in chunks],
        embeddings,
    ]
    col.insert(data)
    col.flush()


def insert_images(doc_id: str, images: list[dict], embeddings: list[list[float]]):
    """插入图片数据"""
    connect()
    col = Collection(IMAGE_COLLECTION)
    data = [
        [doc_id] * len(images),
        [i["path"] for i in images],
        [i["page"] for i in images],
        embeddings,
    ]
    col.insert(data)
    col.flush()


def search_text(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """文本向量检索"""
    connect()
    col = Collection(TEXT_COLLECTION)
    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=["text", "page", "doc_id"],
    )
    hits = []
    for hit in results[0]:
        hits.append({
            "text": hit.entity.get("text"),
            "page": hit.entity.get("page"),
            "doc_id": hit.entity.get("doc_id"),
            "score": hit.score,
        })
    return hits


def search_image(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """图片向量检索"""
    connect()
    col = Collection(IMAGE_COLLECTION)
    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=["image_path", "page", "doc_id"],
    )
    hits = []
    for hit in results[0]:
        hits.append({
            "image_path": hit.entity.get("image_path"),
            "page": hit.entity.get("page"),
            "doc_id": hit.entity.get("doc_id"),
            "score": hit.score,
        })
    return hits


def insert_memories(memories: list[dict], embeddings: list[list[float]]) -> list[int]:
    """插入长期记忆到 memory_collection"""
    connect()
    col = Collection(MEMORY_COLLECTION)
    data = [
        [m["content"] for m in memories],
        [m.get("memory_type", "fact") for m in memories],
        embeddings,
    ]
    ids = col.insert(data).primary_keys
    col.flush()
    return ids


def search_memories(query_embedding: list[float], top_k: int = 3) -> list[dict]:
    """语义检索相关记忆"""
    connect()
    col = Collection(MEMORY_COLLECTION)
    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=["memory_text", "memory_type"],
    )
    hits = []
    for hit in results[0]:
        hits.append({
            "content": hit.entity.get("memory_text"),
            "type": hit.entity.get("memory_type"),
            "score": hit.score,
        })
    return hits


def delete_collection(collection_id: str):
    """删除集合"""
    connect()
    for name in [TEXT_COLLECTION, IMAGE_COLLECTION]:
        if utility.has_collection(name):
            col = Collection(name)
            col.delete(f'doc_id == "{collection_id}"')

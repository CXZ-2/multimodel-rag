from fastapi import APIRouter, HTTPException
from pymilvus import Collection, utility
from backend.core import vectorstore
from backend.models.schemas import CollectionInfo

router = APIRouter()


@router.get("/collections", response_model=list[CollectionInfo])
async def list_collections():
    """列出所有知识库"""
    vectorstore.connect()
    collections = []
    for name in [vectorstore.TEXT_COLLECTION, vectorstore.IMAGE_COLLECTION]:
        if utility.has_collection(name):
            col = Collection(name)
            collections.append(CollectionInfo(
                id=name,
                name="文本知识库" if name == vectorstore.TEXT_COLLECTION else "图片知识库",
                doc_count=col.num_entities,
                created_at="-",
            ))
    return collections


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str):
    """删除知识库"""
    try:
        vectorstore.delete_collection(collection_id)
        return {"message": f"知识库 {collection_id} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

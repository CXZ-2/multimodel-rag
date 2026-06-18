import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from backend.models.database import get_db
from backend.models.conversations import Conversation, Message
from backend.models.schemas import ConversationOut, ConversationDetailOut, MessageOut

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    q = select(Conversation).order_by(Conversation.updated_at.desc()).limit(50)
    rows = (await db.execute(q)).scalars().all()
    result = []
    for c in rows:
        count_q = select(func.count(Message.id)).where(Message.conversation_id == c.id)
        msg_count = (await db.execute(count_q)).scalar()
        result.append(ConversationOut(
            id=str(c.id), title=c.title, created_at=c.created_at,
            updated_at=c.updated_at, message_count=msg_count,
        ))
    return result


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(db: AsyncSession = Depends(get_db)):
    conv = Conversation(id=uuid.uuid4(), title="新的会话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationOut(
        id=str(conv.id), title=conv.title,
        created_at=conv.created_at, updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/conversations/{conv_id}", response_model=ConversationDetailOut)
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    msg_q = select(Message).where(
        Message.conversation_id == conv.id
    ).order_by(Message.created_at)
    messages = (await db.execute(msg_q)).scalars().all()
    return ConversationDetailOut(
        id=str(conv.id), title=conv.title, created_at=conv.created_at,
        messages=[MessageOut(
            id=str(m.id), role=m.role, content=m.content,
            image_base64=m.image_base64, sources=m.sources,
            created_at=m.created_at,
        ) for m in messages],
    )


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}


class AppendMessageRequest(BaseModel):
    role: str = "assistant"
    content: str
    sources: list | None = None
    image_base64: str | None = None


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut)
async def append_message(conv_id: str, req: AppendMessageRequest, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role=req.role,
        content=req.content,
        image_base64=req.image_base64,
        sources=req.sources,
    )
    db.add(msg)

    # 更新会话标题（取第一条用户消息前20字）
    if conv.title == "新的会话":
        title = req.content[:40].replace("\n", " ").strip()
        stmt = update(Conversation).where(Conversation.id == conv.id).values(title=title, updated_at=func.now())
        await db.execute(stmt)

    await db.commit()
    await db.refresh(msg)

    return MessageOut(
        id=str(msg.id), role=msg.role, content=msg.content,
        image_base64=msg.image_base64, sources=msg.sources,
        created_at=msg.created_at,
    )

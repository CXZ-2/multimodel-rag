import asyncio
import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core import agents
from backend.models.schemas import QueryRequest, QueryResponse, SourceItem
from backend.models.database import get_db
from backend.models.conversations import Conversation, Message
from backend.models.documents import Document

router = APIRouter()


def _build_sources(results: list[dict], doc_names: dict[str, str]) -> list[SourceItem]:
    """构建前端来源列表（query 和 query_stream 共用）"""
    sources = []
    for i, r in enumerate(results):
        if "text" in r and r["text"]:
            sources.append(SourceItem(
                type="text", index=i + 1,
                content=r["text"], page=r["page"],
                score=r.get("score", 0),
                doc_name=doc_names.get(r.get("doc_id", ""), r.get("doc_id", "")),
            ))
        elif "image_path" in r:
            sources.append(SourceItem(
                type="image", index=i + 1,
                image_url=r["image_path"], page=r["page"],
                score=r.get("score", 0),
                doc_name=doc_names.get(r.get("doc_id", ""), r.get("doc_id", "")),
            ))
    return sources


async def _resolve_doc_names(results: list[dict], db: AsyncSession) -> dict[str, str]:
    """批量查询 doc_id → filename"""
    doc_ids = {r["doc_id"] for r in results if r.get("doc_id")}
    doc_names: dict[str, str] = {}
    if doc_ids:
        try:
            from uuid import UUID
            uuids = [UUID(d) for d in doc_ids]
            rows = await db.execute(
                select(Document.filename, Document.id).where(Document.id.in_(uuids))
            )
            for filename, did in rows:
                doc_names[str(did)] = filename
        except ValueError:
            pass
    return doc_names


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest, db: AsyncSession = Depends(get_db)):
    """多Agent: Router(LLM) → General Agent / RAG Agent(知识库)"""

    # 加载最近对话历史 + 会话信息
    history: list[dict] = []
    conv = None
    if req.conversation_id:
        from uuid import UUID as _UUID
        stmt = (
            select(Conversation)
            .where(Conversation.id == _UUID(req.conversation_id))
            .options(selectinload(Conversation.messages))
        )
        conv_result = await db.execute(stmt)
        conv = conv_result.scalar_one_or_none()
        if conv and conv.messages:
            for msg in conv.messages[-6:]:
                history.append({"role": msg.role, "content": msg.content[:200]})

    result = agents.chat(req.question, image_base64=req.image_base64, history=history,
                         conversation_id=req.conversation_id)
    answer = result["answer"]
    results = result["sources"]

    doc_names = await _resolve_doc_names(results, db)
    sources = _build_sources(results, doc_names)

    # 保存消息到 PostgreSQL
    if conv:
        is_first_message = len(conv.messages) == 0

        user_msg = Message(
            id=uuid.uuid4(), conversation_id=conv.id, role="user",
            content=req.question, image_base64=req.image_base64,
        )
        db.add(user_msg)
        assistant_msg = Message(
            id=uuid.uuid4(), conversation_id=conv.id, role="assistant",
            content=answer,
            sources=[s.model_dump() for s in sources],
        )
        db.add(assistant_msg)
        if is_first_message:
            conv.title = req.question[:50]
        await db.commit()

        # 短期记忆: 保存到 Redis
        from backend.core.redis_client import add_conversation_turn
        add_conversation_turn(str(conv.id), "user", req.question)
        add_conversation_turn(str(conv.id), "assistant", answer[:500])

        # 长期记忆: 每 8 轮触发一次异步提取
        if len(conv.messages) >= 8 and len(conv.messages) % 4 == 0:
            import json as _json
            recent = [{"role": m.role, "content": m.content}
                      for m in conv.messages[-20:]]
            from backend.core.tasks import extract_conversation_memories
            extract_conversation_memories.delay(
                str(conv.id), _json.dumps(recent, ensure_ascii=False))

    return QueryResponse(answer=answer, sources=sources)


@router.post("/query/stream")
async def query_stream(req: QueryRequest, db: AsyncSession = Depends(get_db)):
    """SSE 流式问答 — agent → sources → token... → done"""

    # 加载对话历史
    history: list[dict] = []
    conv_stream = None
    if req.conversation_id:
        from uuid import UUID as _UUID
        stmt = (
            select(Conversation)
            .where(Conversation.id == _UUID(req.conversation_id))
            .options(selectinload(Conversation.messages))
        )
        conv_result = await db.execute(stmt)
        conv_stream = conv_result.scalar_one_or_none()
        if conv_stream and conv_stream.messages:
            for msg in conv_stream.messages[-6:]:
                history.append({"role": msg.role, "content": msg.content[:200]})

    async def event_generator():
        loop = asyncio.get_event_loop()

        def _collect():
            return list(agents.chat_stream(req.question, req.image_base64, history=history,
                                           conversation_id=req.conversation_id))

        events = await loop.run_in_executor(None, _collect)

        full_answer = ""
        results = []
        agent = ""

        for ev in events:
            if ev["event"] == "token":
                full_answer += ev["data"]
            elif ev["event"] == "agent":
                agent = ev["data"]
            elif ev["event"] == "sources":
                results = ev["data"]

            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"

        # 流式结束后保存到数据库
        if conv_stream and full_answer:
            try:
                is_first_message = len(conv_stream.messages) == 0

                doc_names = await _resolve_doc_names(results, db)
                sources = _build_sources(results, doc_names)

                user_msg = Message(
                    id=uuid.uuid4(), conversation_id=conv_stream.id, role="user",
                    content=req.question, image_base64=req.image_base64,
                )
                db.add(user_msg)
                assistant_msg = Message(
                    id=uuid.uuid4(), conversation_id=conv_stream.id, role="assistant",
                    content=full_answer,
                    sources=[s.model_dump() for s in sources],
                )
                db.add(assistant_msg)
                if is_first_message:
                    conv_stream.title = req.question[:50]
                await db.commit()
            except Exception as e:
                import logging
                logging.getLogger("omnimind").error("流式对话保存失败: %s", e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

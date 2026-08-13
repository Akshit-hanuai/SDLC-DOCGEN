import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Chunk
from app.services.rag.chunker import ChunkRecord
from app.services.rag.embeddings import get_embedder


@dataclass
class SearchHit:
    text: str
    source_doc_type: str
    source_file: str
    heading: str
    req_ids: list[str] = field(default_factory=list)
    distance: float = 1.0


async def index_chunks(session: AsyncSession, project_id: uuid.UUID, records: list[ChunkRecord]) -> int:
    embedder = get_embedder()
    texts = [r.text for r in records]
    vectors = embedder.embed(texts)
    count = 0
    for record, vector in zip(records, vectors):
        session.add(
            Chunk(
                project_id=project_id,
                source_doc_type=record.source_doc_type,
                requirement_id=record.req_ids[0] if record.req_ids else None,
                text=record.text,
                extra={"heading": record.heading, "source_file": record.source_file, "req_ids": record.req_ids},
                embedding=list(vector),
            )
        )
        count += 1
    await session.commit()
    return count


async def clear_chunks(session: AsyncSession, project_id: uuid.UUID) -> None:
    await session.execute(delete(Chunk).where(Chunk.project_id == project_id))
    await session.commit()


async def search(
    session: AsyncSession,
    project_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
    sources: list[str] | None = None,
) -> list[SearchHit]:
    embedder = get_embedder()
    query_vec = list(embedder.embed([query])[0])
    top_k = top_k or 8

    distance = Chunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(Chunk, distance.label("distance"))
        .where(Chunk.project_id == project_id)
        .order_by(distance.asc())
        .limit(top_k * 3)
    )
    if sources:
        stmt = stmt.where(Chunk.source_doc_type.in_(sources))
    result = await session.execute(stmt)
    hits: list[SearchHit] = []
    for chunk, dist in result.all():
        meta = chunk.extra or {}
        hits.append(
            SearchHit(
                text=chunk.text,
                source_doc_type=chunk.source_doc_type,
                source_file=meta.get("source_file", ""),
                heading=meta.get("heading", ""),
                req_ids=meta.get("req_ids", []),
                distance=float(dist),
            )
        )
    return hits[:top_k]

from dataclasses import dataclass, field

from app.services.ingest.models import Block
from app.services.ingest.requirements_extractor import find_req_ids

MAX_CHARS = 800
OVERLAP = 80


@dataclass
class ChunkRecord:
    source_doc_type: str
    source_file: str
    heading: str
    text: str
    req_ids: list[str] = field(default_factory=list)


def chunk_blocks(blocks: list[Block], doc_type: str, filename: str) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    heading_path: list[str] = []
    for block in blocks:
        while heading_path and len(heading_path) >= block.level:
            heading_path.pop()
        if block.heading.strip():
            heading_path.append(block.heading.strip())
        for text in _split_text(block.text):
            if not text.strip():
                continue
            records.append(
                ChunkRecord(
                    source_doc_type=doc_type,
                    source_file=filename,
                    heading=" / ".join(heading_path) if heading_path else filename,
                    text=text.strip(),
                    req_ids=find_req_ids(text),
                )
            )
    return records


def _split_text(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        cut = text.rfind("\n", start, end)
        if cut > start + MAX_CHARS // 2:
            end = cut
        pieces.append(text[start:end])
        start = max(end - OVERLAP, start + 1)
    return pieces

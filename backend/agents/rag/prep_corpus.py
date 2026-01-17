from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from backend.agents.types import CorpusItem, PageContent


def chunk_text(text: str, max_chars: int = 2000, overlap_chars: int = 200) -> List[str]:
    """Simple char-based chunker with overlap.

    Atlas-RAG/AutoSchemaKG accepts raw text or JSONL docs; chunking helps avoid
    long-context loss and keeps provenance intact.
    """
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]

    chunks: List[str] = []
    start = 0
    while start < len(t):
        end = min(len(t), start + max_chars)
        chunk = t[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(t):
            break
        # step forward with overlap
        start = max(0, end - overlap_chars)
    return chunks


def pages_to_corpus_items(pages: Iterable[PageContent], lang: str = "en") -> List[CorpusItem]:
    items: List[CorpusItem] = []
    for page in pages:
        chunks = chunk_text(page.text)
        for ci, chunk in enumerate(chunks):
            item_id = f"{page.doc_id}::chunk{ci}"
            items.append(
                CorpusItem(
                    id=item_id,
                    text=chunk,
                    metadata={
                        "lang": lang,
                        "category": page.category,
                        "source_path": page.source_path,
                        "page": page.page,
                        "images": [
                            {
                                "image_id": im.image_id,
                                "file_path": im.file_path,
                                "page": im.page,
                                "width": im.width,
                                "height": im.height,
                                "ext": im.ext,
                            }
                            for im in page.images
                        ],
                    },
                )
            )
    return items


def write_jsonl(items: Iterable[CorpusItem], out_path: str | Path) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({"id": it.id, "text": it.text, "metadata": it.metadata}, ensure_ascii=False))
            f.write("\n")
    return str(p.resolve())

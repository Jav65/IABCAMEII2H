from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from backend.agents.types import PageContent
from backend.agents.utils.hash import sha256_file


@dataclass
class SourceRecord:
    category: str
    source_path: str
    sha256: str
    num_pages_parsed: int


@dataclass
class JobManifest:
    job_id: str
    created_at_iso: str
    corpus_jsonl: str
    extracted_images_dir: str
    sources: List[SourceRecord]
    # free-form extras, e.g., model names, atlas-rag output dirs, etc.
    extras: Dict[str, object]


def write_manifest(manifest_path: str | Path, manifest: JobManifest) -> None:
    p = Path(manifest_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")


def build_source_records(pages: List[PageContent]) -> List[SourceRecord]:
    """Collapse per-page provenance into per-file provenance for easy auditing."""
    by_file: Dict[str, Dict[str, object]] = {}
    for page in pages:
        rec = by_file.setdefault(
            page.source_path,
            {"category": page.category, "count": 0},
        )
        rec["count"] = int(rec["count"]) + 1

    out: List[SourceRecord] = []
    for source_path, rec in sorted(by_file.items()):
        out.append(
            SourceRecord(
                category=str(rec["category"]),
                source_path=source_path,
                sha256=sha256_file(source_path),
                num_pages_parsed=int(rec["count"]),
            )
        )
    return out

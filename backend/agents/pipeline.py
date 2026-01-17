from __future__ import annotations

import datetime as _dt
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, List, Optional

load_dotenv()  # take environment variables from .env file if present

from backend.agents.types import (
    GeneratedOutput,
    GenerationRequest,
    GroupedFiles,
    ImportantCategory,
    OutputFormat,
    PageContent,
)
from backend.agents.parser import parse_pdf
from backend.agents.rag import pages_to_corpus_items, write_jsonl
from backend.agents.storage.manifest import JobManifest, build_source_records, write_manifest
from backend.agents.clustering import cluster_by_difficulty, load_kg_from_atlasrag
from backend.agents.generation import generate_output


IMPORTANT: List[ImportantCategory] = ["Lectures", "Tutorials", "Labs"]


def run_pipeline(
    grouped_files: GroupedFiles,
    *,
    job_id: str,
    output_root: str | Path = Path(__file__).resolve().parent / "output",
    lang: str = "en",
    output_format: OutputFormat = "cheatsheet",
    run_atlasrag: bool = False,
    atlasrag_base_url: Optional[str] = None,
    atlasrag_api_key: Optional[str] = None,
    atlasrag_model_path: str = "Qwen/Qwen2.5-7B-Instruct",
    use_agentic: bool = False,
    agentic_model: str = "gpt-4-turbo-preview",
) -> str:
    """End-to-end: parse docs -> build KG -> cluster by difficulty -> generate study material.

    Phase 1: Document Parsing
    - Parse PDFs/text documents with image extraction using PyMuPDF
    - Build JSONL corpus for Atlas-RAG

    Phase 2: Knowledge Extraction (Optional)
    - Run Atlas-RAG to extract knowledge graph with AutoSchemaKG
    - Load extracted nodes and edges

    Phase 3: Clustering and Ranking
    - Cluster knowledge by difficulty (basic to advanced)
    - Rank for optimal learning order

    Phase 4: Output Generation
    - Generate cheatsheet, cue cards, or flashcards
    - Use agentic system for cheatsheet if requested

    Returns the absolute path to the job output directory.
    """
    out_dir = Path(output_root) / job_id
    images_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # PHASE 1: Document Parsing
    # =====================================================================
    print(f"[Pipeline] Phase 1: Parsing documents...")
    pages: List[PageContent] = []
    for cat in IMPORTANT:
        for path in grouped_files.get(cat, []):
            p = os.path.join(os.getcwd(), "test_data", path) if not os.path.isabs(path) else path
            p = Path(p)
            ext = p.suffix.lower()

            if ext == ".pdf":
                pages.extend(parse_pdf(p, category=cat, out_image_dir=images_dir, doc_id_prefix=f"{cat}_{p.stem}"))
            elif ext in {".txt", ".md"}:
                text = p.read_text(encoding="utf-8", errors="ignore")
                pages.append(
                    PageContent(
                        doc_id=f"{cat}_{p.stem}",
                        source_path=str(p.resolve()),
                        category=cat,
                        page=0,
                        text=text.strip(),
                        images=[],
                    )
                )
            else:
                # You can extend this with .docx parsing, pptx, images, etc.
                continue

    corpus_items = pages_to_corpus_items(pages, lang=lang)
    corpus_path = write_jsonl(corpus_items, out_dir / "corpus.jsonl")
    
    print(f"[Pipeline] Parsed {len(pages)} pages, {len(corpus_items)} corpus items")

    manifest = JobManifest(
        job_id=job_id,
        created_at_iso=_dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        corpus_jsonl=corpus_path,
        extracted_images_dir=str(images_dir.resolve()),
        sources=build_source_records(pages),
        extras={
            "num_pages": len(pages),
            "num_corpus_items": len(corpus_items),
            "output_format": output_format,
        },
    )

    # =====================================================================
    # PHASE 2: Knowledge Extraction
    # =====================================================================
    kg_nodes = []
    kg_edges = []

    if run_atlasrag:
        print(f"[Pipeline] Phase 2: Running Atlas-RAG KG extraction...")
        from backend.agents.rag import RAGConfig, create_rag
        atlasrag_api_key = os.environ.get("OPENAI_API_KEY")
        print(f"Using OPENAI_API_KEY: {atlasrag_api_key}")
        if not atlasrag_base_url: #or not atlasrag_api_key:
            raise ValueError(
                "run_atlasrag=True requires atlasrag_base_url and atlasrag_api_key (OpenAI-compatible endpoint)."
            )

        # Atlas-RAG loads from a directory; we place the JSONL in a folder and filter with filename_pattern.
        data_dir = str(out_dir.resolve())
        cfg = RAGConfig(
            model_path=atlasrag_model_path,
            data_directory=data_dir,
            filename_pattern="corpus",  # matches corpus.jsonl
            output_directory=str((out_dir / "atlasrag_out").resolve()),
        )
        out_kg_dir = create_rag(
            config=cfg,
            base_url=atlasrag_base_url,
            api_key=atlasrag_api_key,
            model_name=atlasrag_model_path,
        )
        manifest.extras["atlasrag_output_directory"] = out_kg_dir
        
        # Load extracted KG
        kg_nodes, kg_edges = load_kg_from_atlasrag(out_kg_dir)
        print(f"[Pipeline] Extracted {len(kg_nodes)} nodes, {len(kg_edges)} edges")
    else:
        print(f"[Pipeline] Phase 2: Skipped (Atlas-RAG disabled)")
    
    # =====================================================================
    # PHASE 3: Clustering and Difficulty Ranking
    # =====================================================================
    print(f"[Pipeline] Phase 3: Clustering by difficulty...")
    
    outputs_by_category: Dict[ImportantCategory, GeneratedOutput] = {}
    
    if kg_nodes and kg_edges:
        for cat in IMPORTANT:
            # Filter nodes/edges for this category
            cat_nodes = [n for n in kg_nodes if any(cat in src for src in n.source_ids)]
            cat_edges = [e for e in kg_edges 
                        if any(n.node_id == e.source_id for n in cat_nodes) or 
                               any(n.node_id == e.target_id for n in cat_nodes)]
            
            if not cat_nodes:
                continue
            
            print(f"[Pipeline] Clustering {cat}: {len(cat_nodes)} nodes")
            
            # Cluster by difficulty
            clustered = cluster_by_difficulty(cat_nodes, cat_edges, cat)
            
            # =====================================================================
            # PHASE 4: Output Generation
            # =====================================================================
            print(f"[Pipeline] Phase 4: Generating {output_format} for {cat}...")
            
            # Standard template-based generation (always)
            request = GenerationRequest(
                output_format=output_format,
                clustered_knowledge=clustered,
                title=f"{cat} - Study Guide",
            )
            output = generate_output(request, out_dir)
            
            # Attempt agentic refinement (optional, non-blocking)
            if output_format == "cheatsheet" and use_agentic:
                print(f"[Pipeline] Attempting agentic refinement (model: {agentic_model})...")
                from backend.agents.agentic_cheatsheet import generate_agentic_cheatsheet
                
                try:
                    latex_content = generate_agentic_cheatsheet(
                        clustered,
                        title=f"{cat} - Study Guide",
                        model=agentic_model,
                        save_path=out_dir / f"{cat}_cheatsheet_agentic.tex",
                    )
                    output = GeneratedOutput(
                        format="cheatsheet",
                        content=latex_content,
                        metadata={
                            "num_nodes": len(cat_nodes),
                            "num_edges": len(cat_edges),
                            "category": cat,
                            "agentic": True,
                        },
                        output_file=str(out_dir / f"{cat}_cheatsheet_agentic.tex"),
                    )
                    print(f"[Pipeline] ✓ Agentic refinement succeeded")
                except Exception as e:
                    print(f"[Pipeline] ⚠️  Agentic refinement skipped ({type(e).__name__})")
            
            outputs_by_category[cat] = output
            print(f"[Pipeline] Generated {output_format} for {cat}")
    else:
        print(f"[Pipeline] No KG available; skipping clustering and generation")
    
    # =====================================================================
    # Save manifest and summary
    # =====================================================================
    write_manifest(out_dir / "manifest.json", manifest)
    
    # Save generation summary
    if outputs_by_category:
        summary = {
            "job_id": job_id,
            "output_format": output_format,
            "categories": {
                cat: {
                    "format": output.format,
                    "output_file": output.output_file,
                    "num_nodes": output.metadata.get("num_nodes"),
                    "num_edges": output.metadata.get("num_edges"),
                }
                for cat, output in outputs_by_category.items()
            }
        }
        import json
        with open(out_dir / "generation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

    return str(out_dir.resolve())

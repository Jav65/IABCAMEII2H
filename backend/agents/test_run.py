from __future__ import annotations

import argparse
import os
import json
from pathlib import Path

from agents.pipeline import Pipeline, LLMAnalyzer, KnowledgeGraphBuilder, Clusterer, Orderer, CheatsheetGenerator
from agents.types import OutputFormat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline: parse docs -> build KG -> cluster -> generate study materials"
    )
    parser.add_argument(
        "--grouped",
        required=True,
        help="Path to grouped-files JSON (keys: Lectures/Tutorials/Labs/Miscellaneous)",
    )
    parser.add_argument("--job-id", required=True, help="A name for this run (used as output folder)")
    parser.add_argument("--lang", default="en", help="Language code for metadata (default: en)")
    
    # New parameters for clustering and output generation
    parser.add_argument(
        "--output-format",
        choices=["cheatsheet", "cue_card", "flashcard"],
        default="cheatsheet",
        help="Output format: cheatsheet (LaTeX), cue_card (LaTeX), or flashcard (JSON)",
    )
    parser.add_argument(
        "--run-atlasrag",
        default=True,
        action="store_true",
        help="If set, run Atlas-RAG KG construction",
    )
    parser.add_argument(
        "--atlasrag-base-url",
        default=None,
        help="OpenAI-compatible base_url, e.g. http://0.0.0.0:8129/v1",
    )
    parser.add_argument(
        "--atlasrag-api-key",
        default=None,
        help="API key for the endpoint (use EMPTY for local vLLM)",
    )
    parser.add_argument(
        "--atlasrag-model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Model name/path",
    )
    parser.add_argument(
        "--use-agentic",
        default = True,
        action="store_true",
        help="For cheatsheet format: use agentic system with LLM refinement",
    )
    parser.add_argument(
        "--agentic-model",
        default="gpt-4o-mini",
        help="LLM model for agentic generation (if --use-agentic is set)",
    )

    args = parser.parse_args()


    grouped_path = Path(args.grouped)
    grouped = json.loads(grouped_path.read_text(encoding="utf-8"))

    # Convert grouped dict to document list for pipeline
    documents = []
    for category, files in grouped.items():
        for file_path in files:
            documents.append({
                'source_path': os.path.join(os.getcwd(), "test_data", file_path),
                'category': category,
                'out_image_dir': f"{args.job_id}/images"
            })

    # Instantiate pipeline components
    llm = LLMAnalyzer()
    kg_builder = KnowledgeGraphBuilder()
    clusterer = Clusterer()
    orderer = Orderer()
    cheatsheet_generator = CheatsheetGenerator()

    pipeline = Pipeline(
        documents=documents,
        llm=llm,
        kg_builder=kg_builder,
        clusterer=clusterer,
        orderer=orderer,
        cheatsheet_generator=cheatsheet_generator,
    )

    cheatsheet = pipeline.run()

    # Save cheatsheet output
    out_dir = Path(args.job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"cheatsheet.tex"
    output_file.write_text(cheatsheet, encoding="utf-8")
    print(f"✓ Pipeline complete: {output_file}")
    print("\nGenerated files:")
    print(f"  - {output_file.name} ({output_file.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.agents.pipeline import run_pipeline
from backend.agents.types import OutputFormat


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
        default="gpt-4-turbo-preview",
        help="LLM model for agentic generation (if --use-agentic is set)",
    )

    args = parser.parse_args()

    grouped_path = Path(args.grouped)
    grouped = json.loads(grouped_path.read_text(encoding="utf-8"))

    out_dir = run_pipeline(
        grouped,
        job_id=args.job_id,
        lang=args.lang,
        output_format=args.output_format,  # type: ignore
        run_atlasrag=bool(args.run_atlasrag),
        atlasrag_base_url=args.atlasrag_base_url,
        atlasrag_api_key=args.atlasrag_api_key,
        atlasrag_model_path=args.atlasrag_model,
        use_agentic=bool(args.use_agentic),
        agentic_model=args.agentic_model,
    )

    print(f"✓ Pipeline complete: {out_dir}")
    
    # Print summary of generated files
    output_path = Path(out_dir)
    print("\nGenerated files:")
    for file in output_path.glob("*.*"):
        if file.is_file() and file.suffix in [".tex", ".json", ".md"]:
            print(f"  - {file.name} ({file.stat().st_size} bytes)")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


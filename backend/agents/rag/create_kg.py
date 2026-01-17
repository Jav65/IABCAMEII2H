from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RAGConfig:
    """Minimal config wrapper for Atlas-RAG KG construction."""

    model_path: str
    data_directory: str
    filename_pattern: str
    output_directory: str

    # optional knobs (match ProcessingConfig defaults reasonably)
    max_new_tokens: int = 2048
    max_workers: int = 3
    batch_size_triple: int = 3
    batch_size_concept: int = 16
    remove_doc_spaces: bool = True


def create_rag(
    *,
    config: RAGConfig,
    base_url: str,
    api_key: str,
    model_name: Optional[str] = None,
) -> str:
    """Run AutoSchemaKG/Atlas-RAG KG construction with an OpenAI-compatible endpoint.

    Returns the absolute path of the output directory.

    This follows the Atlas-RAG quickstart: construct `LLMGenerator` +
    `KnowledgeGraphExtractor`, then run extraction + conversions.
    """
    try:
        from openai import OpenAI
        from atlas_rag.kg_construction.triple_config import ProcessingConfig
        from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor
        from atlas_rag.llm_generator import LLMGenerator
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Atlas-RAG dependencies not available. Install with `pip install atlas-rag` "
            "and set up your LLM client (OpenAI-compatible)."
        ) from e

    mname = model_name or config.model_path

    client = OpenAI(base_url=base_url, api_key=api_key)
    llm_generator = LLMGenerator(client=client, model_name=mname)

    kg_extraction_config = ProcessingConfig(
        model_path=config.model_path,
        data_directory=config.data_directory,
        filename_pattern=config.filename_pattern,
        output_directory=config.output_directory,
        batch_size_triple=config.batch_size_triple,
        batch_size_concept=config.batch_size_concept,
        max_new_tokens=config.max_new_tokens,
        max_workers=config.max_workers,
        remove_doc_spaces=config.remove_doc_spaces,
    )

    kg_extractor = KnowledgeGraphExtractor(model=llm_generator, config=kg_extraction_config)

    # Pipeline (as documented)
    kg_extractor.run_extraction()
    kg_extractor.convert_json_to_csv()
    kg_extractor.generate_concept_csv_temp()
    kg_extractor.create_concept_csv()
    kg_extractor.convert_to_graphml()

    return str(Path(config.output_directory).resolve())

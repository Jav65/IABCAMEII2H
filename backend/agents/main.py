from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from agents.pipeline import Pipeline, LLMAnalyzer, KnowledgeGraphBuilder, Clusterer, Orderer, Generator
from agents.types import OutputFormat
from categorizer.main import categorize_zip_content 


@dataclass
class AtlasRAGConfig:
    base_url: str
    api_key: str
    model: str


def runner(
        zip_file_path: Path, format: str, output_dir: Path,
        lang: str = "en", use_atlasrag: Optional[AtlasRAGConfig] = None,
    ) -> None:
    # TODO: Differentiate based on format, if the other formats are ready
    # The lang and use_atlasrag parameters are currently unused.

    grouped = categorize_zip_content(zip_file_path)

    # Convert grouped dict to document list for pipeline
    documents = []
    zip_file_dir = zip_file_path.parent
    print(os.listdir(zip_file_dir))
    for category, files in grouped.items():
        for file_path in files:
            documents.append({
                'source_path': zip_file_dir / file_path,
                'category': category,
            })

    # Instantiate pipeline components
    llm = LLMAnalyzer()
    kg_builder = KnowledgeGraphBuilder()
    clusterer = Clusterer()
    orderer = Orderer()
    generator = Generator(output_format=format)

    pipeline = Pipeline(
        documents=documents,
        output_format=format,
        output_dir=output_dir,
        llm=llm,
        kg_builder=kg_builder,
        clusterer=clusterer,
        orderer=orderer,
        generator=generator,
    )

    content, generation_metadata = pipeline.run()

    # Determine file extension based on format
    file_extensions = {
        "cheatsheet": ".tex",
        "keynote": ".json",
        "flashcard": ".json",
    }
    file_ext = file_extensions.get(format, ".json")

    # Save output
    output_file = output_dir / f"{format}{file_ext}"
    output_file.write_text(content, encoding="utf-8")

    # Save generation metadata
    metadata_file = output_dir / f"generation_metadata.json"
    metadata_file.write_text(json.dumps(generation_metadata, indent=2, default=str), encoding="utf-8")
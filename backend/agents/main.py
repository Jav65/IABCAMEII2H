from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from agents.pipeline import Pipeline, LLMAnalyzer, KnowledgeGraphBuilder, Clusterer, Orderer, CheatsheetGenerator
from agents.types import OutputFormat


@dataclass
class AtlasRAGConfig:
    base_url: str
    api_key: str
    model: str


def runner(
        grouped: dict[str, list[Path]], format: str, output_dir: Path,
        lang: str = "en", use_atlasrag: Optional[AtlasRAGConfig] = None,
    ) -> None:
    # TODO: Differentiate based on format, if the other formats are ready
    # The lang and use_atlasrag parameters are currently unused.

    # Convert grouped dict to document list for pipeline
    documents = []
    for category, files in grouped.items():
        for file_path in files:
            documents.append({
                'source_path': file_path,
                'category': category,
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

    output_tex = pipeline.run()

    # Save output
    output_file = output_dir / f"main.tex"
    output_file.write_text(output_tex, encoding="utf-8")
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.types import (
    KGNode,
    KGEdge,
    ClusteredKnowledge,
    ImportantCategory,
)
from backend.agents.clustering import cluster_by_difficulty, KnowledgeGraphBuilder, Clusterer


class LLMAnalyzer:
    """Analyzes documents and extracts topics and important points using LLM."""

    def __init__(self, model="gpt-4o-mini"):
        self.model = model

    def analyze(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse document and extract topics and important points.
        
        Args:
            document: dict with 'source_path', 'category', 'out_image_dir'
            
        Returns:
            dict with 'topics', 'important_points', 'source'
        """
        try:
            from backend.agents.parser import parse_pdf
        except Exception as e:
            print(f"Warning: Could not import parser - {e}")
            return {
                'topics': [],
                'important_points': [],
                'source': document.get('source_path', 'unknown'),
            }

        try:
            pages = parse_pdf(
                source_path=document['source_path'],
                category=document.get('category', 'Lectures'),
                out_image_dir=document.get('out_image_dir', './images'),
            )
            # LLM-based extraction already merges pages and filters unimportant content
        except Exception as e:
            print(f"Warning: Failed to parse {document.get('source_path')} - {e}")
            return {
                'topics': [],
                'important_points': [],
                'source': document.get('source_path', 'unknown'),
            }

        # Extract text from pages
        topics = []
        important_points = []
        
        for page in pages:
            # Simple extraction: use first 100 chars as topic
            topic = page.text[:100].replace('\n', ' ').strip()
            if topic:
                topics.append(topic)
                important_points.append({
                    'label': topic,
                    'description': page.text[:200],
                    'type': 'Concept',
                })

        return {
            'topics': topics,
            'important_points': important_points,
            'source': document['source_path'],
        }


class Orderer:
    """Orders nodes/clusters for optimal learning flow."""

    def order(self, clusters: ClusteredKnowledge) -> ClusteredKnowledge:
        """
        Order nodes within clusters for learning.
        
        Args:
            clusters: ClusteredKnowledge object
            
        Returns:
            Ordered ClusteredKnowledge object
        """
        # Already ordered by difficulty in clustering step
        return clusters


class CheatsheetGenerator:
    """Generates LaTeX cheatsheet from ordered nodes using LLM."""

    def __init__(self, model="gpt-4o-mini"):
        self.model = model

    def generate(self, ordered_nodes: ClusteredKnowledge) -> str:
        """
        Generate LaTeX cheatsheet from ordered nodes using LLM for content blocks.
        
        Args:
            ordered_nodes: ClusteredKnowledge object
            
        Returns:
            LaTeX content as string
        """
        if not isinstance(ordered_nodes, ClusteredKnowledge):
            raise ValueError("ordered_nodes must be a ClusteredKnowledge object")

        title = getattr(ordered_nodes, "category", "Study Cheatsheet")
        
        # Use LLM-powered generation from generation module
        try:
            from backend.agents.generation import _generate_cheatsheet
            return _generate_cheatsheet(ordered_nodes, title)
        except Exception as e:
            print(f"Warning: LLM generation failed - {e}, using fallback")
            return self._generate_fallback_latex(ordered_nodes, title)

    def _generate_fallback_latex(self, knowledge: ClusteredKnowledge, title: str) -> str:
        """Generate basic LaTeX when agentic generator is unavailable."""
        latex = r"""
\documentclass[9pt,a4paper]{article}
\usepackage[margin=0.4in]{geometry}
\usepackage{multicol}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{amssymb}
\usepackage{amsmath}

\title{""" + title.replace("_", "\\_") + r"""}
\author{Generated Study Guide}
\date{}

\begin{document}
\maketitle

\begin{multicols}{3}
"""
        
        # Add sections for each difficulty level
        current_level = -1
        for node in knowledge.nodes:
            diff = knowledge.node_to_difficulty.get(node.node_id)
            level = diff.level if diff else 0
            label = diff.label if diff else "Unknown"
            
            if level != current_level:
                if current_level >= 0:
                    latex += "\n"
                current_level = level
                latex += f"\n\\section*{{{label}}}\n"
            
            # Add node content
            latex += f"\\textbf{{{node.label}}}\n"
            if node.description:
                latex += f"{node.description[:200]}\n\n"
            
            # Add source info
            if node.source_ids:
                latex += f"\\textit{{Source: {', '.join(node.source_ids)}}}\n\n"
        
        latex += r"""
\end{multicols}
\end{document}
"""
        return latex


class Pipeline:
    """End-to-end pipeline: parse docs -> LLM analysis -> KG -> cluster -> order -> cheatsheet."""

    def __init__(
        self,
        documents: List[Dict[str, Any]],
        llm: Optional[LLMAnalyzer] = None,
        kg_builder: Optional[KnowledgeGraphBuilder] = None,
        clusterer: Optional[Clusterer] = None,
        orderer: Optional[Orderer] = None,
        cheatsheet_generator: Optional[CheatsheetGenerator] = None,
    ):
        self.documents = documents
        self.llm = llm or LLMAnalyzer()
        self.kg_builder = kg_builder or KnowledgeGraphBuilder()
        self.clusterer = clusterer or Clusterer()
        self.orderer = orderer or Orderer()
        self.cheatsheet_generator = cheatsheet_generator or CheatsheetGenerator()

    def run(self) -> str:
        """
        Run the full pipeline.
        
        Returns:
            LaTeX cheatsheet content as string
        """
        print("[Pipeline] Starting end-to-end pipeline...")
        
        # Step 1: LLM analysis (parallel processing)
        print("[Pipeline] Step 1: Analyzing documents with LLM (parallel)...")
        doc_infos = []
        
        # Use ThreadPoolExecutor for parallel document processing
        max_workers = min(4, len(self.documents))  # Limit to 4 concurrent threads to avoid API rate limits
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_doc = {executor.submit(self.llm.analyze, doc): doc for doc in self.documents}
            
            # Process results as they complete
            completed = 0
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                completed += 1
                try:
                    info = future.result()
                    doc_infos.append(info)
                    print(f"  ✓ Processed document {completed}/{len(self.documents)}: {doc.get('source_path', 'unknown')}")
                except Exception as e:
                    print(f"  ✗ Failed to analyze {doc.get('source_path', 'unknown')}: {e}")

        if not doc_infos:
            print("[Pipeline] Warning: No documents were successfully analyzed")
            return "% No documents to generate cheatsheet from\n"

        # Step 2: Build knowledge graph
        print("[Pipeline] Step 2: Building knowledge graph...")
        try:
            kg = self.kg_builder.build(doc_infos)
            print(f"  Built KG with {len(kg[0])} nodes, {len(kg[1])} edges")
        except Exception as e:
            print(f"  Error building KG: {e}")
            return "% Error building knowledge graph\n"

        # Step 3: Cluster
        print("[Pipeline] Step 3: Clustering by difficulty...")
        try:
            clusters = self.clusterer.cluster(kg)
            print(f"  Clustered into difficulty levels: {set(d.level for d in clusters.node_to_difficulty.values())}")
        except Exception as e:
            print(f"  Error clustering: {e}")
            return "% Error clustering knowledge\n"

        # Step 4: Order
        print("[Pipeline] Step 4: Ordering nodes...")
        try:
            ordered_nodes = self.orderer.order(clusters)
            print(f"  Ordered {len(ordered_nodes.nodes)} nodes")
        except Exception as e:
            print(f"  Error ordering: {e}")
            return "% Error ordering nodes\n"

        # Step 5: Generate cheatsheet
        print("[Pipeline] Step 5: Generating cheatsheet...")
        try:
            cheatsheet = self.cheatsheet_generator.generate(ordered_nodes)
            print(f"  Generated cheatsheet ({len(cheatsheet)} chars)")
        except Exception as e:
            print(f"  Error generating cheatsheet: {e}")
            return "% Error generating cheatsheet\n"

        print("[Pipeline] ✓ Pipeline complete!")
        return cheatsheet

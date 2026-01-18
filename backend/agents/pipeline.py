from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.types import ClusteredKnowledge
from backend.agents.clustering import KnowledgeGraphBuilder, Clusterer


class LLMAnalyzer:
    """Analyzes documents and extracts topics and important points using LLM."""

    def __init__(self, model="gpt-4o-mini"):
        self.model = model

    def analyze(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse document and extract topics and important points.

        Args:
            document: Dict with 'source_path', 'category', 'out_image_dir'

        Returns:
            Dict with 'topics', 'important_points', 'source'
        """
        try:
            from backend.agents.parser import parse_pdf
        except Exception as e:
            print(f"Warning: Could not import parser - {e}")
            return {
                "topics": [],
                "important_points": [],
                "source": document.get("source_path", "unknown"),
            }

        try:
            parsed_pages = parse_pdf(
                source_path=document["source_path"],
                category=document.get("category", "Lectures"),
                out_image_dir=document.get("out_image_dir", "./images"),
            )
        except Exception as e:
            print(f"Warning: Failed to parse {document.get('source_path')} - {e}")
            return {
                "topics": [],
                "important_points": [],
                "source": (document.get("source_path", "unknown"), document.get("page", 0)),
            }

        topics = []
        important_points = []
        pages = []

        for page in parsed_pages:
            topic = page.text.replace("\n", " ").strip()
            if topic:
                topics.append(topic)
                important_points.append({
                    "label": topic,
                    "description": page.text[:200],
                    "type": "Concept",
                })
                pages.append(page)

        return {
            "topics": topics,
            "important_points": important_points,
            "source": (document["source_path"], pages),
        }


class Orderer:
    """Orders nodes/clusters for optimal learning flow."""

    def order(self, clusters: ClusteredKnowledge) -> ClusteredKnowledge:
        """Order nodes within clusters for learning.

        Args:
            clusters: ClusteredKnowledge object

        Returns:
            Ordered ClusteredKnowledge object
        """
        return clusters


class CheatsheetGenerator:
    """Generates LaTeX cheatsheet from ordered nodes using LLM."""

    def __init__(self, model="gpt-4o-mini"):
        self.model = model

    def generate(self, ordered_nodes: ClusteredKnowledge) -> tuple[str, dict]:
        """Generate LaTeX cheatsheet from ordered nodes using LLM for content blocks.

        Args:
            ordered_nodes: ClusteredKnowledge object

        Returns:
            Tuple of (LaTeX content, generation_metadata dict)
        """
        if not isinstance(ordered_nodes, ClusteredKnowledge):
            raise ValueError("ordered_nodes must be a ClusteredKnowledge object")

        title = getattr(ordered_nodes, "category", "Study Cheatsheet")

        try:
            from backend.agents.generation import _generate_cheatsheet
            return _generate_cheatsheet(ordered_nodes, title)
        except Exception as e:
            print(f"Warning: LLM generation failed - {e}, using fallback")
            return self._generate_fallback_latex(ordered_nodes, title)

    def _generate_fallback_latex(self, knowledge: ClusteredKnowledge, title: str) -> tuple[str, dict]:
        """Generate basic LaTeX when agentic generator is unavailable.
        
        Returns:
            Tuple of (latex content, empty metadata dict)
        """
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

            latex += f"\\textbf{{{node.label}}}\n"
            if node.description:
                latex += f"{node.description[:200]}\n\n"

            if node.source_ids:
                latex += f"\\textit{{Source: {', '.join(str(s) for s in node.source_ids)}}}\n\n"

        latex += r"""
\end{multicols}
\end{document}
"""
        return latex, {}


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

    def run(self) -> tuple[str, dict]:
        """Run the full pipeline.

        Returns:
            Tuple of (LaTeX cheatsheet content, generation_metadata dict)
        """
        print("[Pipeline] Starting end-to-end pipeline...")

        print("[Pipeline] Step 1: Analyzing documents with LLM (parallel)...")
        doc_infos = self._analyze_documents_parallel()
        if not doc_infos:
            print("[Pipeline] Warning: No documents were successfully analyzed")
            return "% No documents to generate cheatsheet from\n", {}

        print("[Pipeline] Step 2: Building knowledge graph...")
        kg = self._build_knowledge_graph(doc_infos)
        if kg is None:
            return "% Error building knowledge graph\n", {}

        print("[Pipeline] Step 3: Clustering by difficulty...")
        clusters = self._cluster_knowledge(kg)
        if clusters is None:
            return "% Error clustering knowledge\n", {}

        print("[Pipeline] Step 4: Ordering nodes...")
        ordered_nodes = self._order_nodes(clusters)
        if ordered_nodes is None:
            return "% Error ordering nodes\n", {}

        print("[Pipeline] Step 5: Generating cheatsheet...")
        result = self._generate_cheatsheet(ordered_nodes)
        if result is None:
            return "% Error generating cheatsheet\n", {}
        
        cheatsheet, metadata = result
        print("[Pipeline] ✓ Pipeline complete!")
        return cheatsheet, metadata

    def _analyze_documents_parallel(self) -> List[Dict[str, Any]]:
        """Analyze documents in parallel using ThreadPoolExecutor."""
        doc_infos = []
        max_workers = min(4, len(self.documents))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {executor.submit(self.llm.analyze, doc): doc for doc in self.documents}
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
        # print(doc_infos)
        return doc_infos

    def _build_knowledge_graph(self, doc_infos: List[Dict[str, Any]]) -> Optional[Tuple]:
        """Build knowledge graph from document infos."""
        try:
            kg = self.kg_builder.build(doc_infos)
            print(f"  Built KG with {len(kg[0])} nodes, {len(kg[1])} edges")
            return kg
        except Exception as e:
            print(f"  Error building KG: {e}")
            return None

    def _cluster_knowledge(self, kg: Tuple) -> Optional[ClusteredKnowledge]:
        """Cluster knowledge by difficulty."""
        try:
            clusters = self.clusterer.cluster(kg)
            print(f"  Clustered into difficulty levels: {set(d.level for d in clusters.node_to_difficulty.values())}")
            return clusters
        except Exception as e:
            print(f"  Error clustering: {e}")
            return None

    def _order_nodes(self, clusters: ClusteredKnowledge) -> Optional[ClusteredKnowledge]:
        """Order nodes for optimal learning flow."""
        try:
            ordered_nodes = self.orderer.order(clusters)
            print(f"  Ordered {len(ordered_nodes.nodes)} nodes")
            return ordered_nodes
        except Exception as e:
            print(f"  Error ordering: {e}")
            return None

    def _generate_cheatsheet(self, ordered_nodes: ClusteredKnowledge) -> Optional[tuple[str, dict]]:
        """Generate cheatsheet from ordered nodes.
        
        Returns:
            Tuple of (cheatsheet content, metadata dict) or None on error
        """
        try:
            cheatsheet, metadata = self.cheatsheet_generator.generate(ordered_nodes)
            print(f"  Generated cheatsheet ({len(cheatsheet)} chars)")
            print(f"  Tracked {len(metadata)} generation blocks")
            return cheatsheet, metadata
        except Exception as e:
            print(f"  Error generating cheatsheet: {e}")
            return None

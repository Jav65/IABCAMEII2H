"""Clustering and difficulty ranking of knowledge graph nodes.

Groups knowledge by concept complexity and ranks from basic to advanced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.agents.types import ClusteredKnowledge, DifficultyLevel, KGEdge, KGNode, ImportantCategory


# Keywords/patterns that indicate difficulty level
FUNDAMENTAL_KEYWORDS = {
    "definition", "basic", "introduction", "fundamental", "what is",
    "overview", "explanation", "concept", "principle", "simple",
    "example", "basic example", "starting", "beginning"
}

INTERMEDIATE_KEYWORDS = {
    "application", "use case", "implementation", "technique", "method",
    "process", "procedure", "how to", "practical", "strategy",
    "system", "framework", "pattern"
}

ADVANCED_KEYWORDS = {
    "optimization", "advanced", "complex", "theorem", "proof",
    "algorithm", "architecture", "design pattern", "performance",
    "edge case", "sophisticated", "research", "extension", "variation"
}

EXPERT_KEYWORDS = {
    "cutting edge", "research frontier", "novel approach", "proprietary",
    "experimental", "specialized variant", "micro-optimization"
}


def infer_node_difficulty(node: KGNode, context_edges: List[KGEdge]) -> int:
    """Infer difficulty level (0-3+) based on node properties and connections.
    
    Returns:
        0: Fundamental
        1: Intermediate
        2: Advanced
        3+: Expert
    """
    combined_text = (
        (node.label + " " + node.description + " " + node.node_type)
        .lower()
    )
    
    # Count keyword matches
    expert_count = sum(1 for kw in EXPERT_KEYWORDS if kw in combined_text)
    advanced_count = sum(1 for kw in ADVANCED_KEYWORDS if kw in combined_text)
    intermediate_count = sum(1 for kw in INTERMEDIATE_KEYWORDS if kw in combined_text)
    
    if expert_count >= 1:
        return 3
    elif advanced_count >= 2:
        return 2
    elif intermediate_count >= 1:
        return 1
    else:
        return 0


def analyze_graph_structure(
    nodes: List[KGNode],
    edges: List[KGEdge],
) -> Dict[str, int]:
    """Analyze graph structure to infer difficulty through connectivity.
    
    Nodes with more incoming edges (dependencies) tend to be more advanced.
    Nodes with no incoming edges or only outgoing edges tend to be foundational.
    """
    node_to_difficulty = {}
    
    # Build adjacency
    in_degree = {node.node_id: 0 for node in nodes}
    out_degree = {node.node_id: 0 for node in nodes}
    
    for edge in edges:
        in_degree[edge.target_id] = in_degree.get(edge.target_id, 0) + 1
        out_degree[edge.source_id] = out_degree.get(edge.source_id, 0) + 1
    
    # Score: high in_degree + low out_degree = advanced
    # High out_degree + low in_degree = foundational
    for node in nodes:
        in_deg = in_degree.get(node.node_id, 0)
        out_deg = out_degree.get(node.node_id, 0)
        
        if in_deg == 0 and out_deg > 0:
            # Foundational: teaches many things but depends on nothing
            score = 0
        elif in_deg > out_deg:
            # Advanced: depends on more things than it teaches
            score = min(in_deg - out_deg + 1, 3)
        elif in_deg > 0:
            # Intermediate
            score = 1
        else:
            # Isolated or equal
            score = 0
        
        node_to_difficulty[node.node_id] = score
    
    return node_to_difficulty


def _topological_sort(
    nodes: List[KGNode],
    edges: List[KGEdge],
) -> List[str]:
    """Simple topological sort for DAG ordering."""
    
    # Build adjacency list
    graph = {node.node_id: [] for node in nodes}
    in_degree = {node.node_id: 0 for node in nodes}
    
    for edge in edges:
        if edge.source_id in graph and edge.target_id in graph:
            graph[edge.source_id].append(edge.target_id)
            in_degree[edge.target_id] += 1
    
    # Kahn's algorithm
    queue = [node_id for node_id in in_degree if in_degree[node_id] == 0]
    result = []
    
    while queue:
        node_id = queue.pop(0)
        result.append(node_id)
        
        for neighbor in graph.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # Add any remaining nodes (cycle or isolated)
    for node in nodes:
        if node.node_id not in result:
            result.append(node.node_id)
    
    return result


def cluster_by_difficulty(
    nodes: List[KGNode],
    edges: List[KGEdge],
    category: ImportantCategory,
) -> ClusteredKnowledge:
    """Cluster knowledge graph nodes by difficulty level and rank them.
    
    1. Infer difficulty from node properties
    2. Refine using graph structure analysis
    3. Perform topological ordering within each difficulty level
    4. Return clustered knowledge ranked from basic to advanced
    """
    
    # Step 1: Keyword-based difficulty inference
    node_to_difficulty = {
        node.node_id: infer_node_difficulty(node, edges)
        for node in nodes
    }
    
    # Step 2: Refine using graph structure
    structural_scores = analyze_graph_structure(nodes, edges)
    for node_id in node_to_difficulty:
        # Blend keyword-based and structural scores
        keyword_score = node_to_difficulty[node_id]
        structural_score = structural_scores.get(node_id, 0)
        node_to_difficulty[node_id] = max(keyword_score, structural_score)
    
    # Step 3: Create DifficultyLevel objects
    difficulty_labels = {
        0: "Fundamentals",
        1: "Core Concepts",
        2: "Advanced Topics",
        3: "Expert Knowledge",
    }
    
    node_to_difficulty_obj = {
        node_id: DifficultyLevel(
            level=level,
            label=difficulty_labels.get(level, f"Level {level}"),
        )
        for node_id, level in node_to_difficulty.items()
    }
    
    # Step 4: Topological ordering for better reading flow
    topo_order = _topological_sort(nodes, edges)
    
    # Sort nodes: first by difficulty, then by topological order
    sorted_nodes = sorted(
        nodes,
        key=lambda n: (
            node_to_difficulty.get(n.node_id, 0),
            topo_order.index(n.node_id) if n.node_id in topo_order else float('inf')
        )
    )
    
    return ClusteredKnowledge(
        nodes=sorted_nodes,
        edges=edges,
        node_to_difficulty=node_to_difficulty_obj,
        category=category,
    )


def load_kg_from_atlasrag(kg_dir: str | Path) -> tuple[List[KGNode], List[KGEdge]]:
    """Load knowledge graph from Atlas-RAG output directory.
    
    Atlas-RAG typically outputs:
    - schema.json: node and edge type definitions
    - entities.jsonl: node instances
    - relations.jsonl: edge instances
    """
    kg_dir = Path(kg_dir)
    nodes = []
    edges = []
    
    # Try to load entities
    entities_file = kg_dir / "entities.jsonl"
    if entities_file.exists():
        with open(entities_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                
                # Atlas-RAG format may vary; adapt as needed
                node_id = data.get("id") or data.get("name")
                node_label = data.get("label") or data.get("name")
                node_type = data.get("type") or "Entity"
                description = data.get("description") or data.get("text", "")
                properties = {k: v for k, v in data.items() 
                            if k not in {"id", "name", "label", "type", "description", "text"}}
                source_ids = data.get("source_ids", [])
                
                if node_id and node_label:
                    nodes.append(KGNode(
                        node_id=node_id,
                        label=node_label,
                        node_type=node_type,
                        description=description,
                        properties=properties,
                        source_ids=source_ids if isinstance(source_ids, list) else [source_ids],
                    ))
    
    # Try to load relations
    relations_file = kg_dir / "relations.jsonl"
    if relations_file.exists():
        with open(relations_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                
                source_id = data.get("source") or data.get("head")
                target_id = data.get("target") or data.get("tail")
                relation_type = data.get("relation") or data.get("type", "related_to")
                properties = {k: v for k, v in data.items()
                            if k not in {"source", "target", "relation", "type", "head", "tail"}}
                
                if source_id and target_id:
                    edges.append(KGEdge(
                        source_id=source_id,
                        target_id=target_id,
                        relation_type=relation_type,
                        properties=properties,
                    ))
    
    return nodes, edges

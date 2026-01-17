"""Clustering and difficulty ranking of knowledge graph nodes.

Groups knowledge by concept complexity and ranks from basic to advanced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.types import ClusteredKnowledge, DifficultyLevel, KGEdge, KGNode, ImportantCategory


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


def _compute_text_similarity(text1: str, text2: str) -> float:
    """Compute text similarity based on word overlap (Jaccard similarity).
    
    Returns a score between 0 and 1.
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


def _semantic_cluster_nodes(nodes: List[KGNode], similarity_threshold: float = 0.3) -> Dict[str, List[KGNode]]:
    """Cluster nodes by semantic similarity.
    
    Groups nodes with similar labels and descriptions together.
    
    Args:
        nodes: List of KGNode objects
        similarity_threshold: Minimum similarity score to group nodes
        
    Returns:
        Dict mapping cluster_id -> list of nodes in that cluster
    """
    clusters = {}
    cluster_counter = 0
    assigned = set()
    
    for i, node_i in enumerate(nodes):
        if node_i.node_id in assigned:
            continue
        
        # Start new cluster with this node
        cluster_id = f"cluster_{cluster_counter}"
        cluster_nodes = [node_i]
        assigned.add(node_i.node_id)
        cluster_counter += 1
        
        # Find similar nodes
        combined_text_i = f"{node_i.label} {node_i.description}".lower()
        
        for j, node_j in enumerate(nodes[i+1:], start=i+1):
            if node_j.node_id in assigned:
                continue
            
            combined_text_j = f"{node_j.label} {node_j.description}".lower()
            similarity = _compute_text_similarity(combined_text_i, combined_text_j)
            
            if similarity >= similarity_threshold:
                cluster_nodes.append(node_j)
                assigned.add(node_j.node_id)
        
        clusters[cluster_id] = cluster_nodes
    
    return clusters


def _extract_cluster_main_topic(cluster_nodes: List[KGNode]) -> str:
    """Extract main topic for a cluster using LLM.
    
    Summarizes the cluster's content into a single main topic.
    """
    if not cluster_nodes:
        return "Unknown Topic"
    
    if len(cluster_nodes) == 1:
        return cluster_nodes[0].label
    
    try:
        from agents.generation import _extract_topic
        
        node_summaries = [f"- {node.label}: {node.description[:100]}" for node in cluster_nodes]
        combined_text = "\n".join(node_summaries)
        
        main_topic = _extract_topic(combined_text)
        return main_topic if main_topic else cluster_nodes[0].label
    except Exception as e:
        print(f"Warning: Could not extract main topic with LLM - {e}, using heuristic")
        # Fallback: use the most descriptive node's label
        return max(cluster_nodes, key=lambda n: len(n.description or "")).label


def _infer_cluster_difficulty(main_topic: str, cluster_nodes: List[KGNode]) -> int:
    """Infer difficulty level for a cluster based on its main topic and nodes.
    
    Returns:
        0: Fundamental
        1: Intermediate
        2: Advanced
        3+: Expert
    """
    combined_text = main_topic + " " + " ".join([n.label + " " + n.description for n in cluster_nodes])
    combined_text = combined_text.lower()
    
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
    """Revised clustering pipeline:
    
    1. Create semantic clusters of similar nodes
    2. Extract main topic for each cluster using LLM
    3. Assign difficulty to clusters (not individual nodes)
    4. Order clusters from basic to advanced
    5. Return ordered ClusteredKnowledge with cluster metadata
    """
    
    if not nodes:
        return ClusteredKnowledge(
            nodes=[],
            edges=[],
            node_to_difficulty={},
            category=category,
            cluster_metadata={},
        )
    
    # Step 1: Semantic clustering
    print("[Clustering] Step 1: Performing semantic clustering...")
    semantic_clusters = _semantic_cluster_nodes(nodes, similarity_threshold=0.3)
    print(f"[Clustering] Created {len(semantic_clusters)} semantic clusters")
    
    # Step 2: Extract main topics and assign cluster difficulty
    print("[Clustering] Step 2: Extracting main topics and inferring cluster difficulty...")
    cluster_to_main_topic = {}
    cluster_to_difficulty = {}
    node_id_to_cluster = {}
    
    for cluster_id, cluster_nodes in semantic_clusters.items():
        main_topic = _extract_cluster_main_topic(cluster_nodes)
        cluster_to_main_topic[cluster_id] = main_topic
        
        difficulty_level = _infer_cluster_difficulty(main_topic, cluster_nodes)
        cluster_to_difficulty[cluster_id] = difficulty_level
        
        for node in cluster_nodes:
            node_id_to_cluster[node.node_id] = cluster_id
        
        print(f"  Cluster {cluster_id}: '{main_topic}' (difficulty: {difficulty_level})")
    
    # Step 3: Create difficulty level objects for nodes based on their cluster
    print("[Clustering] Step 3: Assigning difficulty levels to nodes...")
    difficulty_labels = {
        0: "Fundamentals",
        1: "Core Concepts",
        2: "Advanced Topics",
        3: "Expert Knowledge",
    }
    
    node_to_difficulty_obj = {}
    for node in nodes:
        cluster_id = node_id_to_cluster.get(node.node_id)
        cluster_diff = cluster_to_difficulty.get(cluster_id, 0)
        node_to_difficulty_obj[node.node_id] = DifficultyLevel(
            level=cluster_diff,
            label=difficulty_labels.get(cluster_diff, f"Level {cluster_diff}"),
        )
    
    # Step 4: Order clusters from basic to advanced
    print("[Clustering] Step 4: Ordering clusters by difficulty...")
    sorted_clusters = sorted(
        semantic_clusters.items(),
        key=lambda item: cluster_to_difficulty[item[0]]
    )
    
    # Step 5: Build ordered node list preserving cluster grouping
    print("[Clustering] Step 5: Building ordered node list...")
    ordered_nodes = []
    cluster_metadata = {}
    
    for cluster_id, cluster_nodes in sorted_clusters:
        ordered_nodes.extend(cluster_nodes)
        
        # Store cluster metadata for use in generation
        cluster_metadata[cluster_id] = {
            "main_topic": cluster_to_main_topic[cluster_id],
            "difficulty": cluster_to_difficulty[cluster_id],
            "node_ids": [node.node_id for node in cluster_nodes],
            "node_count": len(cluster_nodes),
        }
    
    # Add cluster metadata to node properties for reference
    for node in ordered_nodes:
        cluster_id = node_id_to_cluster.get(node.node_id)
        if cluster_id:
            node.properties["cluster_id"] = cluster_id
            node.properties["cluster_main_topic"] = cluster_to_main_topic[cluster_id]
    
    print(f"[Clustering] Complete! Ordered into {len(sorted_clusters)} difficulty-ranked clusters")
    
    return ClusteredKnowledge(
        nodes=ordered_nodes,
        edges=edges,
        node_to_difficulty=node_to_difficulty_obj,
        category=category,
        cluster_metadata=cluster_metadata,
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

class KnowledgeGraphBuilder:
    def build(self, doc_infos):
        """
        Build a knowledge graph from LLM-extracted document infos.
        Each info should have 'important_points' and 'source'.
        Returns nodes and edges.
        """
        nodes = []
        edges = []
        # Create nodes and keep mapping for edge heuristics
        node_map = {}  # (doc_idx, point_idx) -> node_id
        for idx, info in enumerate(doc_infos):
            points = info.get('important_points', []) or []
            for i, point in enumerate(points):
                node_id = f"doc{idx}_point{i}"
                label = point.get('label', point if isinstance(point, str) else str(point)) if isinstance(point, dict) or isinstance(point, str) else str(point)
                desc = point.get('description', '') if isinstance(point, dict) else (point if isinstance(point, str) else '')
                nodes.append(KGNode(
                    node_id=node_id,
                    label=label,
                    node_type=point.get('type', 'Concept') if isinstance(point, dict) else 'Concept',
                    description=desc,
                    properties={},
                    source_ids=[info.get('source')],
                ))
                node_map[(idx, i)] = {
                    'node_id': node_id,
                    'label': str(label),
                    'description': str(desc),
                    'source': info.get('source')
                }

        # Heuristic edges:
        # 1) Sequential 'follows' edges within the same document
        for (doc_idx, i), node in list(node_map.items()):
            next_key = (doc_idx, i + 1)
            if next_key in node_map:
                edges.append(KGEdge(
                    source_id=node['node_id'],
                    target_id=node_map[next_key]['node_id'],
                    relation_type='follows',
                    properties={},
                ))

        # 2) 'related_to' edges when one node's label appears in another node's description
        #    This catches explicit mentions and creates basic semantic links.
        labels = {k: v['label'].lower() for k, v in node_map.items()}
        for a_key, a in node_map.items():
            a_desc = (a.get('description') or '').lower()
            for b_key, b in node_map.items():
                if a_key == b_key:
                    continue
                b_label = b.get('label', '').lower()
                if b_label and b_label in a_desc:
                    # a mentions b -> a related_to b
                    edges.append(KGEdge(
                        source_id=a['node_id'],
                        target_id=b['node_id'],
                        relation_type='related_to',
                        properties={'heuristic': 'mention'},
                    ))

        # Deduplicate edges by (source,target,relation_type)
        seen = set()
        unique_edges = []
        for e in edges:
            key = (e.source_id, e.target_id, e.relation_type)
            if key in seen:
                continue
            seen.add(key)
            unique_edges.append(e)

        # Determine category (use first doc's category if available)
        category = 'Lectures'
        if doc_infos:
            first = doc_infos[0]
            cat = first.get('category') or first.get('source_category')
            if cat:
                category = cat

        return nodes, unique_edges, category

class Clusterer:
    def cluster(self, kg):
        """
        Cluster nodes using existing cluster_by_difficulty logic.
        kg should be a tuple (nodes, edges, category)
        """
        if isinstance(kg, dict):
            nodes = kg.get('nodes', [])
            edges = kg.get('edges', [])
            category = kg.get('category', 'Lectures')
        elif isinstance(kg, tuple):
            if len(kg) == 3:
                nodes, edges, category = kg
            elif len(kg) == 2:
                nodes, edges = kg
                category = 'Lectures'
            else:
                nodes, edges, category = [], [], 'Lectures'
        else:
            nodes, edges, category = [], [], 'Lectures'
        return cluster_by_difficulty(nodes, edges, category)

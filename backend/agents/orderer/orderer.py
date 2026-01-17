from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx


@dataclass(frozen=True)
class TopicBlock:
    """A cheatsheet section: a cluster of related nodes ordered by difficulty."""

    title: str
    node_ids: List[str]
    level: int  # lower = more basic
    evidence: Dict[str, object]


def _find_graphml(output_directory: str | Path) -> Path:
    out = Path(output_directory)
    candidates = list(out.rglob("*.graphml"))
    if not candidates:
        raise FileNotFoundError(f"No .graphml found under {out}")
    # pick the most recent
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def build_order(output_directory: str | Path) -> List[TopicBlock]:
    """Derive a basic->advanced ordering from the induced schema.

    Heuristic approach:
    - Load GraphML produced by Atlas-RAG.
    - Look for edges that look like type / is-a relations.
    - Topologically sort concept DAG to define levels.
    - Fall back to centrality-based ordering if no clear type edges exist.
    """
    graph_path = _find_graphml(output_directory)
    G = nx.read_graphml(graph_path)

    # Identify candidate "type" edges. Different exports may use different labels.
    rel_keys = ["relation", "rel", "type", "predicate", "label"]
    isa_values = {"is_a", "isa", "instance_of", "type_of", "subclass_of", "subClassOf"}

    isa_edges: List[Tuple[str, str]] = []
    for u, v, data in G.edges(data=True):
        rel = None
        for k in rel_keys:
            if k in data:
                rel = str(data[k])
                break
        if rel is None:
            continue
        rel_norm = rel.strip().replace(" ", "_").lower()
        if rel_norm in isa_values:
            # if u is_a v, then v is more basic than u (v comes first)
            isa_edges.append((v, u))  # basic -> advanced

    if isa_edges:
        D = nx.DiGraph()
        D.add_edges_from(isa_edges)
        # remove cycles defensively
        try:
            order = list(nx.topological_sort(D))
        except nx.NetworkXUnfeasible:
            # Break cycles by repeatedly removing one edge from a found cycle.
            # This keeps the ordering usable even if the export contains noisy type edges.
            D2 = D.copy()
            for _ in range(1000):
                try:
                    cycle = nx.find_cycle(D2, orientation="original")
                except nx.NetworkXNoCycle:
                    break
                u, v = cycle[0][0], cycle[0][1]
                if D2.has_edge(u, v):
                    D2.remove_edge(u, v)
            order = list(nx.topological_sort(D2))
            D = D2

        # assign level by longest-path depth from roots
        roots = [n for n in D.nodes() if D.in_degree(n) == 0]
        level: Dict[str, int] = {r: 0 for r in roots}
        for n in order:
            preds = list(D.predecessors(n))
            if not preds:
                level.setdefault(n, 0)
            else:
                level[n] = 1 + max(level.get(p, 0) for p in preds)

        blocks: List[TopicBlock] = []
        for n in order:
            blocks.append(
                TopicBlock(
                    title=str(n),
                    node_ids=[str(n)],
                    level=int(level.get(n, 0)),
                    evidence={"graphml": str(graph_path), "method": "schema_toposort"},
                )
            )
        return blocks

    # Fallback: use centrality (more central often = more fundamental), then reverse for advanced
    und = G.to_undirected()
    cent = nx.degree_centrality(und)
    ranked = sorted(cent.items(), key=lambda kv: kv[1], reverse=True)

    blocks: List[TopicBlock] = []
    for i, (node, score) in enumerate(ranked[:200]):
        blocks.append(
            TopicBlock(
                title=str(node),
                node_ids=[str(node)],
                level=i,  # best-effort ordering
                evidence={"graphml": str(graph_path), "method": "degree_centrality", "score": float(score)},
            )
        )
    return blocks

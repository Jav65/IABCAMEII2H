from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


Category = Literal["Lectures", "Tutorials", "Labs", "Miscellaneous"]
ImportantCategory = Literal["Lectures", "Tutorials", "Labs"]
OutputFormat = Literal["cheatsheet", "cue_card", "flashcard"]


class GroupedFiles(TypedDict, total=False):
    Lectures: List[str]
    Tutorials: List[str]
    Labs: List[str]
    Miscellaneous: List[str]


@dataclass(frozen=True)
class ImageRef:
    image_id: str
    file_path: str  # absolute path on disk where we saved the extracted image, to change into database if got time
    page: int
    width: int
    height: int
    ext: str


@dataclass(frozen=True)
class PageContent:
    doc_id: str
    source_path: str
    category: ImportantCategory
    page: int
    text: str
    images: List[ImageRef]


@dataclass(frozen=True)
class CorpusItem:
    """Atlas-RAG JSONL item.

    Matches the documented JSONL format: {id, text, metadata}.
    """

    id: str
    text: str
    metadata: Dict[str, object]


@dataclass(frozen=True)
class KGNode:
    """Knowledge graph node extracted by Atlas-RAG."""
    
    node_id: str
    label: str
    node_type: str  # e.g., "Concept", "Definition", "Example"
    description: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)  # which corpus items this came from


@dataclass(frozen=True)
class KGEdge:
    """Knowledge graph edge/relationship."""
    
    source_id: str
    target_id: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DifficultyLevel:
    """Ranked difficulty level for clustering."""
    
    level: int  # 0 = basic, 1 = intermediate, 2 = advanced, 3+ = expert
    label: str  # "Fundamentals", "Core Concepts", "Advanced Topics", etc.


@dataclass
class ClusteredKnowledge:
    """Knowledge clustered and ranked by difficulty."""
    
    nodes: List[KGNode]
    edges: List[KGEdge]
    node_to_difficulty: Dict[str, DifficultyLevel]  # maps node_id to difficulty
    category: ImportantCategory
    
    
@dataclass
class GenerationRequest:
    """Request to generate output (cheatsheet, cue card, flashcard)."""
    
    output_format: OutputFormat
    clustered_knowledge: ClusteredKnowledge
    title: str = "Study Guide"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedOutput:
    """Generated study material."""
    
    format: OutputFormat
    content: str  # LaTeX, Markdown, or HTML depending on format
    metadata: Dict[str, Any] = field(default_factory=dict)
    output_file: Optional[str] = None  # path where content was written


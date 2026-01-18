"""Cheatsheet Generation System - Architecture and Usage Guide

## Overview

This system generates study materials (cheatsheets, cue cards, flashcards) from educational documents
using a multi-phase pipeline:

1. **Document Parsing**: Extract text and images from PDFs using PyMuPDF
2. **Knowledge Extraction**: Build knowledge graph using Atlas-RAG (AutoSchemaKG)
3. **Clustering & Ranking**: Sort knowledge by difficulty (basic → advanced)
4. **Output Generation**: Create study materials in LaTeX or JSON format
5. **Agentic Refinement** (Optional): Use LLMs to enhance cheatsheet quality

## Project Structure

```
backend/
├── agents/
│   ├── types.py              # Data structures (KGNode, KGEdge, etc.)
│   ├── clustering.py         # Difficulty ranking & clustering
│   ├── generation.py         # LaTeX/JSON output generation
│   ├── agentic_cheatsheet.py # LLM-based refinement
│   ├── pipeline.py           # Main orchestration (4 phases)
│   ├── parser/
│   │   └── parser.py         # PDF/text parsing with PyMuPDF
│   ├── rag/
│   │   ├── prep_corpus.py    # Corpus chunking for Atlas-RAG
│   │   └── create_kg.py      # KG extraction
│   └── storage/
│       └── manifest.py       # Job metadata
└── server/
    └── main.py               # FastAPI endpoints
```

## Data Flow

### Input
```python
GroupedFiles = {
    "Lectures": ["/path/to/lecture1.pdf", ...],
    "Tutorials": ["/path/to/tutorial1.pdf", ...],
    "Labs": ["/path/to/lab1.pdf", ...],
}
```

### Pipeline Phases

#### Phase 1: Document Parsing
- Input: GroupedFiles with PDF/text paths
- Process: PyMuPDF extracts text & images per page
- Output: List[PageContent] with text, images, metadata

#### Phase 2: Knowledge Extraction
- Input: JSONL corpus from Phase 1
- Process: Atlas-RAG extracts concepts, definitions, relationships
- Output: KGNodes (concepts) and KGEdges (relationships)

#### Phase 3: Clustering & Ranking
- Input: KG nodes and edges
- Process:
  - Keyword-based difficulty inference (0=Fundamental, 1=Intermediate, 2=Advanced, 3=Expert)
  - Graph structure analysis (in-degree/out-degree ratios)
  - Topological ordering within difficulty levels
- Output: ClusteredKnowledge (nodes sorted by difficulty)

#### Phase 4: Output Generation
- Input: ClusteredKnowledge + output_format (cheatsheet/cue_card/flashcard)
- Process:
  - **cheatsheet**: Multi-column LaTeX with sections by difficulty
  - **cue_card**: Individual LaTeX cards (front/back)
  - **flashcard**: JSON format for Anki/Quizlet compatibility
- Output: GeneratedOutput (file + content)

#### Phase 4b: Agentic Refinement (Optional)
- Input: ClusteredKnowledge
- Process:
  - LLM analyzes knowledge structure
  - Generates learning objectives
  - Creates well-structured LaTeX sections
  - Iteratively refines content
- Output: Enhanced LaTeX cheatsheet

## Usage

### Python API

```python
from agents.pipeline import run_pipeline
from agents.types import GroupedFiles

grouped_files: GroupedFiles = {
    "Lectures": ["/path/to/lecture1.pdf"],
    "Tutorials": ["/path/to/tutorial1.pdf"],
    "Labs": ["/path/to/lab1.pdf"],
}

output_dir = run_pipeline(
    grouped_files=grouped_files,
    job_id="course_2024",
    output_format="cheatsheet",
    run_atlasrag=True,
    use_agentic=False,  # Set True for LLM refinement
    atlasrag_base_url="http://localhost:8001",
    atlasrag_api_key="your-key",
)

# Outputs:
# - {output_dir}/Lectures_cheatsheet.tex
# - {output_dir}/Tutorials_cheatsheet.tex
# - {output_dir}/Labs_cheatsheet.tex
# - {output_dir}/generation_summary.json
```

### FastAPI Endpoints

#### 1. Submit Generation Request
```bash
curl -X POST http://localhost:8000/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "grouped_files": {
      "Lectures": ["/path/to/lecture1.pdf"],
      "Tutorials": ["/path/to/tutorial1.pdf"],
      "Labs": ["/path/to/lab1.pdf"]
    },
    "output_format": "cheatsheet",
    "run_atlasrag": true,
    "use_agentic": false
  }'

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "output_format": "cheatsheet",
  "message": "Job ... queued for processing"
}
```

#### 2. Check Job Status
```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": "Pipeline completed successfully",
  "output_directory": "/path/to/output/550e8400-e29b-41d4-a716-446655440000",
  "result_files": {
    ".tex": ["/path/to/Lectures_cheatsheet.tex"],
    ".json": ["/path/to/manifest.json"]
  }
}
```

#### 3. Download Results
```bash
curl http://localhost:8000/jobs/{job_id}/download/latex -o cheatsheet.tex
curl http://localhost:8000/jobs/{job_id}/download/json -o flashcard.json
```

## Configuration

### Environment Variables

For **Atlas-RAG KG Extraction**:
```bash
ATLASRAG_BASE_URL=http://localhost:8001
ATLASRAG_API_KEY=your-key
ATLASRAG_MODEL=Qwen/Qwen2.5-7B-Instruct
```

For **Agentic Refinement** (LLM-based):
```bash
OPENAI_API_KEY=your-key
# or for Azure:
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Pipeline Parameters

```python
run_pipeline(
    grouped_files: GroupedFiles,          # Documents grouped by type
    job_id: str,                          # Unique job identifier
    output_root: Path = "./output",       # Where to save results
    lang: str = "en",                     # Document language
    output_format: OutputFormat = "cheatsheet",  # cheatsheet|cue_card|flashcard
    run_atlasrag: bool = False,           # Enable KG extraction
    use_agentic: bool = False,            # Enable LLM refinement
    agentic_model: str = "gpt-4-turbo-preview",  # LLM model
)
```

## Output Formats

### 1. Cheatsheet (LaTeX)
- Multi-column layout
- Sections by difficulty level
- Colored boxes for visual hierarchy
- Suitable for printing or PDF conversion

Example:
```
┌─────────────────────────────────┐
│ FUNDAMENTALS                    │
├─────────────────────────────────┤
│ ┌─ Definition of X             │
│ │ [description]                │
│ └─ Basic Example               │
│ ┌─ Key Principle               │
│ │ [explanation]                │
│ └─                              │
├─────────────────────────────────┤
│ CORE CONCEPTS                   │
├─────────────────────────────────┤
│ [more advanced topics]          │
└─────────────────────────────────┘
```

### 2. Cue Cards (LaTeX)
- One concept per page
- Front: Term + Type
- Back: Definition
- Suitable for printing as actual cards

### 3. Flashcards (JSON)
- Anki/Quizlet compatible format
- Tags, difficulty levels
- Source references
- Suitable for digital learning apps

Example:
```json
{
  "title": "Course Name",
  "category": "Lectures",
  "cards": [
    {
      "id": "concept_123",
      "front": "What is X?",
      "back": "X is ...",
      "difficulty": 0,
      "difficulty_label": "Fundamentals",
      "tags": ["Lectures", "Definition"]
    }
  ]
}
```

## Difficulty Ranking Algorithm

The system ranks knowledge from basic to advanced using a multi-faceted approach:

### 1. Keyword Analysis
- **Fundamental**: "definition", "basic", "introduction", "principle"
- **Intermediate**: "application", "implementation", "technique", "process"
- **Advanced**: "optimization", "algorithm", "architecture", "theorem"
- **Expert**: "cutting edge", "research", "proprietary"

### 2. Graph Structure Analysis
```
Foundational nodes:
- High out-degree (teach many things)
- Low in-degree (depend on few)
- Example: Basic algebra concepts

Advanced nodes:
- High in-degree (depend on many prerequisites)
- Low out-degree (specialized)
- Example: Complex algorithms
```

### 3. Topological Ordering
Within each difficulty level, concepts are ordered using topological sort to ensure prerequisites come before dependent concepts.

## Example Workflow

```python
# 1. Parse documents (Phase 1)
pages = parse_pdf("lecture.pdf", category="Lectures")
corpus = pages_to_corpus_items(pages)

# 2. Extract knowledge graph (Phase 2)
kg_nodes, kg_edges = load_kg_from_atlasrag("./atlasrag_output")

# 3. Cluster by difficulty (Phase 3)
clustered = cluster_by_difficulty(kg_nodes, kg_edges, "Lectures")

# 4. Generate output (Phase 4)
request = GenerationRequest(
    output_format="cheatsheet",
    clustered_knowledge=clustered,
    title="Lecture Notes Cheatsheet"
)
output = generate_output(request, "./output")

# 5. (Optional) Use LLM refinement
if use_lm:
    from agents.agentic_cheatsheet import generate_agentic_cheatsheet
    enhanced = generate_agentic_cheatsheet(clustered, title="...")
```

## Dependencies

Required packages (see requirements.txt):
- `fitz` (PyMuPDF): PDF parsing
- `atlas-rag`: Knowledge graph extraction
- `fastapi`: Web API
- `openai`: LLM API (for agentic refinement)
- `neo4j`: Graph database (optional)
- `networkx`: Graph algorithms
- `pandas`: Data manipulation

## Troubleshooting

### Atlas-RAG Connection Error
```
Error: "run_atlasrag=True requires atlasrag_base_url and atlasrag_api_key"
```
Solution: Set environment variables or pass parameters:
```python
run_pipeline(
    ...,
    atlasrag_base_url="http://localhost:8001",
    atlasrag_api_key="your-key",
)
```

### LLM API Error (Agentic Mode)
```
Error: "OPENAI_API_KEY not set"
```
Solution: Set API key before running:
```bash
export OPENAI_API_KEY=sk-...
# or
export AZURE_OPENAI_API_KEY=your-key
```

### Empty Output
- Check that input documents contain text (not scanned images)
- Verify Atlas-RAG is properly extracting entities
- Lower min_chars_per_page threshold in ParseOptions

## Performance Considerations

1. **Document Parsing**: ~10-30s per 100-page PDF
2. **Atlas-RAG KG Extraction**: ~2-5 minutes depending on corpus size
3. **Clustering**: <1s for typical corpus
4. **Output Generation**: <1s (template) or 30-60s (agentic with LLM)

Optimize by:
- Processing documents in batches
- Caching Atlas-RAG output for reuse
- Using faster models for agentic mode (e.g., GPT-3.5-turbo)

## Future Enhancements

- [ ] Database backend for job persistence
- [ ] Parallel document processing
- [ ] Support for more document types (.docx, .pptx, images)
- [ ] PDF generation from LaTeX
- [ ] Multi-language support
- [ ] Interactive web UI for previewing
- [ ] Custom CSS styling for HTML output
- [ ] Integration with learning management systems (LMS)
"""

# This file serves as documentation; see ../README.md for project overview

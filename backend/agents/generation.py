"""Generate study materials in various formats from clustered knowledge.

Supports: cheatsheet (LaTeX), key_notes (LaTeX/Markdown), flashcard (JSON).
"""

from __future__ import annotations

import json
from dotenv import load_dotenv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.types import ClusteredKnowledge, GeneratedOutput, GenerationRequest, OutputFormat

load_dotenv()

def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    text = text.replace("\\", "\\textbackslash{}")  # Do this first
    for char, replacement in {k: v for k, v in replacements.items() if k != "\\"}.items():
        text = text.replace(char, replacement)
    return text


def _sanitize_text_for_latex(text: str, max_length: int = 500) -> str:
    """Sanitize and truncate text for LaTeX inclusion."""
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."
    return _escape_latex(text)


def _generate_block_with_llm(node_label: str, node_description: str, node_type: str, model: str = "gpt-4o-mini") -> str:
    print("[Generation] Generating block for node:", node_label)
    """Generate a concise block summary using LLM, filtering unimportant content.
    
    Args:
        node_label: The concept/term label
        node_description: The description/definition
        node_type: Type of node (Concept, Definition, etc.)
        model: LLM model to use
        
    Returns:
        Concise summary suitable for LaTeX cheatsheet, or empty string if unimportant
    """
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _sanitize_text_for_latex(node_description, max_length=300)
        
        client = OpenAI(api_key=api_key)
        prompt = f"""You are a study guide editor. Evaluate and summarize content for a cheatsheet.

Term: {node_label}
Type: {node_type}
Content: {node_description}

Task:
1. Is this content important and educational and relevant to "Information Security"? (yes/no)
2. If yes, provide a concise definition/explanation.
3. If no, respond with: SKIP

Omit fluff, irrelevant images, formatting details, and redundant information, course or assignment details. Focus on core concepts  and materials only.

Output:
Just output the concise summary or "SKIP" if unimportant. No explanations. No Answer of yes and no of whether it is important.
"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        summary = response.choices[0].message.content.strip()
        
        # Check if LLM decided to skip this block
        if "SKIP" in summary.upper() or summary.lower().startswith("no"):
            return ""
        
        return _sanitize_text_for_latex(summary, max_length=500)
    except Exception as e:
        print(f"[Generation] Warning: LLM block generation failed - {e}, using fallback")
        return _sanitize_text_for_latex(node_description, max_length=500)

def _generate_notes_with_llm(node_label: str, node_description: str, node_type: str, model: str = "gpt-4o-mini") -> str:
    print("[Generation] Generating block for node:", node_label)
    """Generate a concise block summary using LLM, filtering unimportant content.
    
    Args:
        node_label: The concept/term label
        node_description: The description/definition
        node_type: Type of node (Concept, Definition, etc.)
        model: LLM model to use
        
    Returns:
        Concise summary suitable for LaTeX cheatsheet, or empty string if unimportant
    """
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _sanitize_text_for_latex(node_description, max_length=300)
        
        client = OpenAI(api_key=api_key)
        prompt = f"""
Act as a JSON formatting assistant. Convert the following input data into a structured JSON object.

**Input Data:**
- Node Label: "{node_label}"
- Node Description: "{node_description}"

**Output Requirements:**
1. **Structure:** Return a single JSON object (not a list).
2. **Title Field:** Create a "title" field. Derive this from the "Node Label" provided above, but shorten it to be concise (max 5 words).
3. **Key Takeaways Field:** Create a "keyTakeaways" field, which must be an array of objects.
4. **Extraction:** Analyze the "Node Description" text. Extract key concepts or steps and format them into the "keyTakeaways" array.
5. **Item Format:** Each item in the array must have:
   - "label": A short name for the specific concept found in the description.
   - "description": The explanation of that concept.
6. **Exclusions:** Do NOT include course administration details (e.g., instructor names, room numbers, exam dates, grading policies) in the "keyTakeaways". If the description contains *only* administrative info, return an empty "keyTakeaways" array [].
7. **Formatting:** Return raw JSON only. Do NOT use Markdown formatting, backticks, or code blocks (e.g., do not start with ```json).

**Example Output Format:**
{{
  "title": "Shortened Title",
  "keyTakeaways": [
    {{
      "label": "Concept 1",
      "description": "Explanation of concept 1..."
    }}
  ]
}}
"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8192,
        )
        summary = response.choices[0].message.content.strip()
        
        return json.loads(summary)
    except Exception as e:
        print(f"[Generation] Warning: LLM block generation failed - {e}, using fallback")
        return node_description

def _generate_flashcard_with_llm(node_label: str, node_description: str, node_type: str, model: str = "gpt-4o-mini") -> str:
    print("[Generation] Generating block for node:", node_label)
    """Generate a concise block summary using LLM, filtering unimportant content.
    
    Args:
        node_label: The concept/term label
        node_description: The description/definition
        node_type: Type of node (Concept, Definition, etc.)
        model: LLM model to use
        
    Returns:
        Concise summary suitable for LaTeX cheatsheet, or empty string if unimportant
    """
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _sanitize_text_for_latex(node_description, max_length=300)
        
        client = OpenAI(api_key=api_key)
        prompt = f"""You are a data processing assistant specialized in educational synthesis. Your goal is to extract "high-yield" study material from input text and return it in a strict JSON format.

**Input Data:**
Label: {node_label}
Description: {node_description}

**Filtering Rules (Critical):**
1. **Ignore Administrative Data:** Do not create objects for syllabus details, dates, instructor names, office hours, submission guidelines, or file formats.
2. **Focus on Core Concepts:** Only extract definitions, formulas, distinct facts, and cause-and-effect relationships.
3. **Handling Noise:** If the input text contains *only* administrative data or non-essential fluff, return an empty array `[]`.

**Output Format:**
* Return **only** a valid JSON array of objects.
* Do not include markdown formatting (like ```json), explanations, or conversational text.
* Each object must have exactly two keys: "front" and "back".
* **Front:** The question or concept name.
* **Back:** The definition, answer, or explanation.

**Schema:**
[
  {{
    "front": "string",
    "back": "string"
  }}
]

**Example 1 (Mixed Content):**
Input Label: Biology 101
Input Description: "Assignments are due Friday. Mitosis is the process of cell division that results in two genetically identical daughter cells."
Output: `[{{"front": "Mitosis", "back": "The process of cell division resulting in two genetically identical daughter cells."}}]`

**Example 2 (Purely Admin):**
Input Label: Chemistry Syllabus
Input Description: "Please upload PDFs only. Late work is -10%."
Output: `[]`
"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8192,
        )
        summary = response.choices[0].message.content.strip()
        
        return json.loads(summary)
    except Exception as e:
        print(f"[Generation] Warning: LLM block generation failed - {e}, using fallback")
        return node_description


def _generate_cheatsheet(knowledge: ClusteredKnowledge, title: str) -> tuple[str, Dict[str, List]]:
    """Generate a LaTeX cheatsheet from clustered knowledge.
    
    Layout: Multi-column format with sections by difficulty level.
    Returns: (latex_content, metadata_dict) where metadata maps "start-end" -> source_ids
    """
    
    latex_header = r"""
\documentclass[8pt,a4paper,landscape]{article}

\usepackage[margin=0.5in]{geometry}
\usepackage{multicol}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage[most]{tcolorbox}
\tcbuselibrary{breakable}
\usepackage{xcolor}
\usepackage{hyperref}

\color{black}

\fancyhf{}
\fancyhead[C]{\textbf{""" + _escape_latex(title) + r"""}}
\fancyfoot[C]{Page \thepage\ of \pageref{LastPage}}
\pagestyle{fancy}

\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}

% Helps multi-column layouts look better when content breaks
\raggedcolumns

\tcbset{
    enhanced,
    breakable,
    colback=white,
    colframe=gray!30,
    coltext=black,
    boxrule=0.5pt,
    left=3pt,
    right=3pt,
    top=3pt,
    bottom=3pt,
    fonttitle=\bfseries,
}

% Difficulty-colored section titles
\newcommand{\difftext}[2]{%
  \begingroup
  \ifnum#1=0 \color{green!60!black}\fi
  \ifnum#1=1 \color{blue!60!black}\fi
  \ifnum#1=2 \color{orange!60!black}\fi
  \ifnum#1>2 \color{red!60!black}\fi
  #2%
  \endgroup
}

\begin{document}
\thispagestyle{fancy}

\begin{multicols}{3}
"""

    
    # Group nodes by difficulty
    nodes_by_difficulty: Dict[int, List] = {}
    print("Assigning nodes to difficulty levels...")
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        if diff:
            level = diff.level
            if level not in nodes_by_difficulty:
                nodes_by_difficulty[level] = []
            nodes_by_difficulty[level].append(node)
    
    # Generate sections and track metadata
    latex_content = latex_header
    block_metadata: Dict[str, List] = {}  # Maps "start-end" -> source_ids
    
    for difficulty_level in sorted(nodes_by_difficulty.keys()):
        nodes = nodes_by_difficulty[difficulty_level]
        diff_obj = knowledge.node_to_difficulty.get(nodes[0].node_id)
        section_label = diff_obj.label if diff_obj else f"Level {difficulty_level}"

        latex_content += f"\n\\subsection*{{\\difftext{{{difficulty_level}}}{{{_escape_latex(section_label)}}}}}\n"
        
        for node in nodes:
            node_title = _escape_latex(node.label)
            node_desc = _generate_block_with_llm(node.label, node.description, node.node_type)
            
            # Skip blocks with empty/unimportant content
            if not node_desc or node_desc.strip() == "":
                continue
            
            node_type = _escape_latex(node.node_type)
            
            # Track line numbers before adding block
            start_line = latex_content.count('\n') + 1
            
            block_content = f"""
\\begin{{tcolorbox}}[title={node_title}, breakable]
\\textit{{{node_type}}} \\\\
{node_desc}
\\end{{tcolorbox}}
"""
            latex_content += block_content
            
            # Track line numbers after adding block
            end_line = latex_content.count('\n')
            
            # Store metadata: line range -> source_ids
            block_key = f"{start_line}-{end_line}"
            block_metadata[block_key] = node.source_ids[0]

    
    latex_content += r"""
\end{multicols}
\end{document}
"""
    
    return latex_content, block_metadata

def _generate_notes_with_llm(node_label: str, node_description: str, node_type: str, model: str = "gpt-4o-mini") -> str:
    print("[Generation] Generating block for node:", node_label)
    """Generate a concise block summary using LLM, filtering unimportant content.
    
    Args:
        node_label: The concept/term label
        node_description: The description/definition
        node_type: Type of node (Concept, Definition, etc.)
        model: LLM model to use
        
    Returns:
        Concise summary suitable for LaTeX cheatsheet, or empty string if unimportant
    """
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _sanitize_text_for_latex(node_description, max_length=300)
        
        client = OpenAI(api_key=api_key)
        prompt = f"""
Act as a JSON formatting assistant. Convert the following input data into a structured JSON object.

**Input Data:**
- Node Label: "{node_label}"
- Node Description: "{node_description}"

**Output Requirements:**
1. **Structure:** Return a single JSON object (not a list).
2. **Title Field:** Create a "title" field. Derive this from the "Node Label" provided above, but shorten it to be concise (max 5 words).
3. **Key Takeaways Field:** Create a "keyTakeaways" field, which must be an array of objects.
4. **Extraction:** Analyze the "Node Description" text. Extract key concepts or steps and format them into the "keyTakeaways" array.
5. **Item Format:** Each item in the array must have:
   - "label": A short name for the specific concept found in the description.
   - "description": The explanation of that concept.
6. **Exclusions:** Do NOT include course administration details (e.g., instructor names, room numbers, exam dates, grading policies) in the "keyTakeaways". If the description contains *only* administrative info, return an empty "keyTakeaways" array [].
7. **Formatting:** Return raw JSON only. Do NOT use Markdown formatting, backticks, or code blocks (e.g., do not start with ```json).

**Example Output Format:**
{{
  "title": "Shortened Title",
  "keyTakeaways": [
    {{
      "label": "Concept 1",
      "description": "Explanation of concept 1..."
    }}
  ]
}}
"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8192,
        )
        summary = response.choices[0].message.content.strip()
        
        return json.loads(summary)
    except Exception as e:
        print(f"[Generation] Warning: LLM block generation failed - {e}, using fallback")
        return node_description

def _generate_flashcard_with_llm(node_label: str, node_description: str, node_type: str, model: str = "gpt-4o-mini"):
    print("[Generation] Generating block for node:", node_label)
    """Generate a concise block summary using LLM, filtering unimportant content.
    
    Args:
        node_label: The concept/term label
        node_description: The description/definition
        node_type: Type of node (Concept, Definition, etc.)
        model: LLM model to use
        
    Returns:
        Concise summary suitable for LaTeX cheatsheet, or empty string if unimportant
    """
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _sanitize_text_for_latex(node_description, max_length=300)
        
        client = OpenAI(api_key=api_key)
        prompt = f"""You are a data processing assistant specialized in educational synthesis. Your goal is to extract "high-yield" study material from input text and return it in a strict JSON format.

**Input Data:**
Label: {node_label}
Description: {node_description}

**Filtering Rules (Critical):**
1. **Ignore Administrative Data:** Do not create objects for syllabus details, dates, instructor names, office hours, submission guidelines, or file formats.
2. **Focus on Core Concepts:** Only extract definitions, formulas, distinct facts, and cause-and-effect relationships.
3. **Handling Noise:** If the input text contains *only* administrative data or non-essential fluff, return an empty array `[]`.

**Output Format:**
* Return **only** a valid JSON array of objects.
* Do not include markdown formatting (like ```json), explanations, or conversational text.
* Each object must have exactly two keys: "front" and "back".
* **Front:** The question or concept name.
* **Back:** The definition, answer, or explanation.

**Schema:**
[
  {{
    "front": "string",
    "back": "string"
  }}
]

**Example 1 (Mixed Content):**
Input Label: Biology 101
Input Description: "Assignments are due Friday. Mitosis is the process of cell division that results in two genetically identical daughter cells."
Output: `[{{"front": "Mitosis", "back": "The process of cell division resulting in two genetically identical daughter cells."}}]`

**Example 2 (Purely Admin):**
Input Label: Chemistry Syllabus
Input Description: "Please upload PDFs only. Late work is -10%."
Output: `[]`
"""
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8192,
        )
        summary = response.choices[0].message.content.strip()
        
        return json.loads(summary)
    except Exception as e:
        print(f"[Generation] Warning: LLM block generation failed - {e}, using fallback")
        return node_description


def _generate_keynote(knowledge: ClusteredKnowledge, title: str):
    """Generate key notes in LaTeX format.
    
    One card per node, with front (term) and back (definition).
    """
    
    nodes_by_difficulty: Dict[int, List] = {}
    print("Assigning nodes to difficulty levels...")
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        if diff:
            level = diff.level
            if level not in nodes_by_difficulty:
                nodes_by_difficulty[level] = []
            nodes_by_difficulty[level].append(node)
    
    content = []
    
    for difficulty_level in sorted(nodes_by_difficulty.keys()):
        nodes = nodes_by_difficulty[difficulty_level]
        
        for node in nodes:
            additional = _generate_notes_with_llm(node.label, node.description, node.node_type)
            if len(additional["keyTakeaways"]) > 0:
                content += [additional]
    
    return json.dumps(content, indent=2), {}

def _generate_flashcard(knowledge: ClusteredKnowledge, title: str) -> str:
    """Generate flashcards in JSON format for interactive tools.
    
    Suitable for Anki, Quizlet, or custom flashcard apps.
    """

    nodes_by_difficulty: Dict[int, List] = {}
    print("Assigning nodes to difficulty levels...")
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        if diff:
            level = diff.level
            if level not in nodes_by_difficulty:
                nodes_by_difficulty[level] = []
            nodes_by_difficulty[level].append(node)
    
    content = []
    
    for difficulty_level in sorted(nodes_by_difficulty.keys()):
        nodes = nodes_by_difficulty[difficulty_level]
        
        for node in nodes:
            additional = _generate_flashcard_with_llm(node.label, node.description, node.node_type)
            content += additional
        
    return json.dumps(content, indent=2), {}


def generate_output(request: GenerationRequest, output_path: Optional[str | Path] = None) -> GeneratedOutput:
    """Generate study material based on request.
    
    Args:
        request: GenerationRequest with format, knowledge, and metadata
        output_path: Optional path to write generated content
        
    Returns:
        GeneratedOutput with generated content and metadata
    """
    
    title = request.title
    knowledge = request.clustered_knowledge
    
    # Generate content based on format (all functions now return tuples)
    generation_metadata: Dict[str, List] = {}
    if request.output_format == "cheatsheet":
        content, generation_metadata = _generate_cheatsheet(knowledge, title)
        file_ext = ".tex"
    elif request.output_format == "keynote":
        content, generation_metadata = _generate_keynote(knowledge, title)
        file_ext = ".json"
    elif request.output_format == "flashcard":
        content, generation_metadata = _generate_flashcard(knowledge, title)
        file_ext = ".json"
    else:
        raise ValueError(f"Unknown output format: {request.output_format}")
    
    # Write to file if path provided
    output_file = None
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_name = f"{knowledge.category}_{request.output_format}{file_ext}"
        output_file = str(output_path / file_name)

        if file_ext == ".json":
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(json.loads(content), f, ensure_ascii=False, indent=2)
        else:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
        
    
    return GeneratedOutput(
        format=request.output_format,
        content=content,
        metadata={
            "num_nodes": len(knowledge.nodes),
            "num_edges": len(knowledge.edges),
            "category": knowledge.category,
            "title": title,
            "generation_metadata": generation_metadata,
        },
        output_file=output_file,
    )


def generate_all_formats(
    knowledge: ClusteredKnowledge,
    output_dir: str | Path,
    title: str = "Study Guide",
) -> Dict[OutputFormat, GeneratedOutput]:
    """Generate all output formats for the given knowledge.
    
    Useful for creating a comprehensive study package.
    """
    
    results: Dict[OutputFormat, GeneratedOutput] = {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for fmt in ["cheatsheet", "keynote", "flashcard"]:
        request = GenerationRequest(
            output_format=fmt,  # type: ignore
            clustered_knowledge=knowledge,
            title=title,
        )
        results[fmt] = generate_output(request, output_dir)  # type: ignore
    
    return results

def generate_one_format(
    knowledge: ClusteredKnowledge,
    output_dir: str | Path,
    title: str = "Study Guide",
    selected_format: OutputFormat = "cheatsheet",
) -> Dict[OutputFormat, GeneratedOutput]:
    """Generate all output formats for the given knowledge.
    
    Useful for creating a comprehensive study package.
    """
    
    results: Dict[OutputFormat, GeneratedOutput] = {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for fmt in ["cheatsheet", "keynote", "flashcard"]:
        if selected_format != fmt:
            continue
        request = GenerationRequest(
            output_format=fmt,  # type: ignore
            clustered_knowledge=knowledge,
            title=title,
        )
        results[fmt] = generate_output(request, output_dir)  # type: ignore
    
    return results

"""Generate study materials in various formats from clustered knowledge.

Supports: cheatsheet (LaTeX), cue_card (LaTeX/Markdown), flashcard (JSON).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agents.types import ClusteredKnowledge, GeneratedOutput, GenerationRequest, OutputFormat


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


def _generate_cheatsheet(knowledge: ClusteredKnowledge, title: str) -> str:
    """Generate a LaTeX cheatsheet from clustered knowledge.
    
    Layout: Multi-column format with sections by difficulty level.
    """
    
    latex_header = r"""
\documentclass[10pt,a4paper]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{multicol}
\usepackage{xcolor}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage{tcolorbox}
\usepackage{hyperref}

\fancyhf{}
\fancyhead[C]{\textbf{""" + _escape_latex(title) + r"""}}
\fancyfoot[C]{Page \thepage\ of \pageref{LastPage}}
\pagestyle{fancy}

\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}

\tcbset{
    fonttitle=\bfseries,
    colback=white,
    colframe=gray!30,
    boxrule=0.5pt,
    left=3pt,
    right=3pt,
    top=3pt,
    bottom=3pt,
}

\newcommand{\diffcolor}[1]{%
    \ifnum#1=0 \color{green!60!black}\else
    \ifnum#1=1 \color{blue!60!black}\else
    \ifnum#1=2 \color{orange!60!black}\else
    \color{red!60!black}\fi\fi\fi
}

\begin{document}

\thispagestyle{fancy}

\begin{multicols}{2}
"""
    
    # Group nodes by difficulty
    nodes_by_difficulty: Dict[int, List] = {}
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        if diff:
            level = diff.level
            if level not in nodes_by_difficulty:
                nodes_by_difficulty[level] = []
            nodes_by_difficulty[level].append(node)
    
    # Generate sections
    latex_content = latex_header
    
    for difficulty_level in sorted(nodes_by_difficulty.keys()):
        nodes = nodes_by_difficulty[difficulty_level]
        diff_obj = knowledge.node_to_difficulty.get(nodes[0].node_id)
        section_label = diff_obj.label if diff_obj else f"Level {difficulty_level}"
        
        latex_content += f"\n\\subsection*{{\\diffcolor{{{difficulty_level}}}{section_label}}}\n"
        
        for node in nodes:
            node_title = _escape_latex(node.label)
            node_desc = _sanitize_text_for_latex(node.description, max_length=300)
            node_type = _escape_latex(node.node_type)
            
            latex_content += f"""
\\begin{{tcolorbox}}[title={node_title}]
\\textit{{{node_type}}} \\\\
{node_desc}
\\end{{tcolorbox}}
"""
    
    latex_content += r"""
\end{multicols}
\end{document}
"""
    
    return latex_content


def _generate_cue_card(knowledge: ClusteredKnowledge, title: str) -> str:
    """Generate cue cards in LaTeX format.
    
    One card per node, with front (term) and back (definition).
    """
    
    latex_header = r"""
\documentclass[12pt,a4paper]{article}
\usepackage[margin=0.3in]{geometry}
\usepackage{tcolorbox}
\usepackage{pagecolor}
\usepackage{tikz}

\tcbset{
    colback=white,
    colframe=black,
    boxrule=2pt,
    width=0.9\textwidth,
    left=10pt,
    right=10pt,
    top=10pt,
    bottom=10pt,
    fonttitle=\large\bfseries,
}

\setlength{\parindent}{0pt}

\title{""" + _escape_latex(title) + r""" - Cue Cards}
\date{}

\begin{document}
"""
    
    latex_content = latex_header
    
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        difficulty_label = f" [{diff.label}]" if diff else ""
        
        front = _escape_latex(node.label) + difficulty_label
        back = _sanitize_text_for_latex(node.description, max_length=800)
        node_type = _escape_latex(node.node_type)
        
        latex_content += f"""
\\newpage
\\begin{{tcolorbox}}[title=FRONT]
\\Large \\textbf{{{front}}} \\\\
\\small \\textit{{{node_type}}}
\\end{{tcolorbox}}

\\vspace{{2cm}}

\\begin{{tcolorbox}}[title=BACK]
{back}
\\end{{tcolorbox}}
"""
    
    latex_content += r"""
\end{document}
"""
    
    return latex_content


def _generate_flashcard(knowledge: ClusteredKnowledge, title: str) -> str:
    """Generate flashcards in JSON format for interactive tools.
    
    Suitable for Anki, Quizlet, or custom flashcard apps.
    """
    
    flashcards = {
        "title": title,
        "category": knowledge.category,
        "cards": []
    }
    
    for node in knowledge.nodes:
        diff = knowledge.node_to_difficulty.get(node.node_id)
        
        card = {
            "id": node.node_id,
            "front": node.label,
            "back": node.description,
            "type": node.node_type,
            "difficulty": diff.level if diff else 0,
            "difficulty_label": diff.label if diff else "Unknown",
            "tags": [knowledge.category, node.node_type],
            "sources": node.source_ids,
        }
        flashcards["cards"].append(card)
    
    return json.dumps(flashcards, indent=2, ensure_ascii=False)


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
    
    # Generate content based on format
    if request.output_format == "cheatsheet":
        content = _generate_cheatsheet(knowledge, title)
        file_ext = ".tex"
    elif request.output_format == "cue_card":
        content = _generate_cue_card(knowledge, title)
        file_ext = ".tex"
    elif request.output_format == "flashcard":
        content = _generate_flashcard(knowledge, title)
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
    
    for fmt in ["cheatsheet", "cue_card", "flashcard"]:
        request = GenerationRequest(
            output_format=fmt,  # type: ignore
            clustered_knowledge=knowledge,
            title=title,
        )
        results[fmt] = generate_output(request, output_dir)  # type: ignore
    
    return results

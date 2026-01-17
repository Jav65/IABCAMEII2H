"""Agentic system for generating high-quality LaTeX cheatsheets using LLMs.

Uses an agentic approach to:
1. Analyze clustered knowledge
2. Identify key learning objectives
3. Generate well-structured LaTeX with better pedagogy
4. Iteratively refine content
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.types import ClusteredKnowledge


def _get_openai_client():
    """Get OpenAI client (or compatible endpoint)."""
    try:
        from openai import OpenAI, AzureOpenAI
    except ImportError:
        raise ImportError("openai package required for agentic cheatsheet generation")
    
    # Try standard OpenAI first
    api_key = None
    api_key_env = None
    
    import os
    if "OPENAI_API_KEY" in os.environ:
        api_key = os.environ["OPENAI_API_KEY"]
    elif "AZURE_OPENAI_API_KEY" in os.environ:
        # Azure setup
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ["AZURE_OPENAI_API_KEY"]
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        return AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )
    
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY or AZURE_OPENAI_API_KEY environment variable not set. "
            "Required for agentic cheatsheet generation."
        )
    
    return OpenAI(api_key=api_key)


class AgenticCheatsheetGenerator:
    """Agentic system for generating high-quality cheatsheets."""
    
    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        max_iterations: int = 3,
    ):
        """Initialize generator.
        
        Args:
            model: LLM model to use (OpenAI compatible)
            temperature: Sampling temperature for generation
            max_iterations: Max refinement iterations
        """
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.client = _get_openai_client()
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call LLM and extract response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=4000,
        )
        return response.choices[0].message.content
    
    def _analyze_knowledge(self, knowledge: ClusteredKnowledge) -> Dict[str, Any]:
        """Use LLM to analyze knowledge structure and extract learning objectives."""
        
        # Prepare knowledge summary
        nodes_summary = "\n".join([
            f"- {node.label} ({knowledge.node_to_difficulty.get(node.node_id).label if knowledge.node_to_difficulty.get(node.node_id) else 'Unknown'}): {node.description[:100]}"
            for node in knowledge.nodes[:20]  # Limit for context
        ])
        
        prompt = f"""Analyze the following educational content and extract key learning objectives.

Content:
{nodes_summary}

Task:
1. Identify 3-5 main learning objectives
2. Suggest sections/categories for organizing the cheatsheet
3. Recommend visual elements or formatting for clarity
4. Suggest connections between concepts

Respond in JSON format:
{{
    "objectives": ["objective1", "objective2", ...],
    "sections": ["section1", "section2", ...],
    "visual_recommendations": ["recommendation1", ...],
    "concept_connections": ["concept1 relates to concept2 because...", ...]
}}
"""
        
        response = self._call_llm([
            {"role": "system", "content": "You are an expert educational content designer."},
            {"role": "user", "content": prompt},
        ])
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback if response isn't valid JSON
            return {
                "objectives": ["Understand key concepts"],
                "sections": ["Fundamentals", "Applications", "Advanced Topics"],
                "visual_recommendations": ["Use colors for different difficulty levels"],
                "concept_connections": [],
            }
    
    def _generate_section_content(
        self,
        section_name: str,
        nodes: List,
        knowledge: ClusteredKnowledge,
        iteration: int = 0,
    ) -> str:
        """Generate LaTeX content for a section using LLM."""
        
        nodes_text = "\n".join([
            f"* {node.label}: {node.description[:200]}"
            for node in nodes[:10]
        ])
        
        refinement_hint = ""
        if iteration > 0:
            refinement_hint = f"\nIteration {iteration}: Improve clarity and add more concrete examples."
        
        prompt = f"""Generate a well-structured, concise LaTeX section for a cheatsheet.

Section: {section_name}
Concepts:
{nodes_text}

Requirements:
1. Use concise, clear language
2. Include 1-2 examples or applications
3. Use LaTeX \section, \subsection, \textbf, \textit as needed
4. Keep it under 1000 characters
5. Make it suitable for quick reference
6. Escape LaTeX special characters properly{refinement_hint}

Generate ONLY the LaTeX content (no document preamble).
"""
        
        content = self._call_llm([
            {"role": "system", "content": "You are an expert at creating concise, clear educational content."},
            {"role": "user", "content": prompt},
        ])
        
        return content
    
    def _build_latex_document(
        self,
        title: str,
        analysis: Dict[str, Any],
        section_contents: Dict[str, str],
        knowledge: ClusteredKnowledge,
    ) -> str:
        """Assemble final LaTeX cheatsheet document."""
        
        header = r"""
\documentclass[9pt,a4paper]{article}
\usepackage[margin=0.4in]{geometry}
\usepackage{multicol}
\usepackage{xcolor}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage{tcolorbox}
\usepackage{hyperref}
\usepackage{amssymb}
\usepackage{amsmath}

\fancyhf{}
\fancyhead[C]{\textbf{""" + title.replace("_", "\\_") + r"""}}
\fancyfoot[C]{\scriptsize Page \thepage\ of \pageref{LastPage}}
\pagestyle{fancy}

\setlength{\parindent}{0pt}
\setlength{\parskip}{3pt}
\setlength{\columnseprule}{0.5pt}

\tcbset{
    fonttitle=\bfseries\small,
    colback=white,
    colframe=gray!40,
    boxrule=0.5pt,
    left=4pt,
    right=4pt,
    top=4pt,
    bottom=4pt,
}

\definecolor{fundamental}{RGB}{76,175,80}
\definecolor{intermediate}{RGB}{33,150,243}
\definecolor{advanced}{RGB}{255,152,0}
\definecolor{expert}{RGB}{244,67,54}

\begin{document}
\thispagestyle{fancy}
\begin{multicols}{3}
"""
        
        # Add objectives
        if analysis.get("objectives"):
            header += r"\section*{Learning Objectives}" + "\n"
            for obj in analysis["objectives"][:3]:
                header += f"$\\bullet$ {obj}\\\\\n"
            header += "\n"
        
        # Add sections
        body = ""
        for section_name in analysis.get("sections", []):
            if section_name in section_contents:
                body += f"\n\\section*{{{section_name}}}\n"
                body += section_contents[section_name]
                body += "\n"
        
        footer = r"""
\end{multicols}
\end{document}
"""
        
        return header + body + footer
    
    def generate(
        self,
        knowledge: ClusteredKnowledge,
        title: str = "Study Cheatsheet",
        save_path: Optional[str | Path] = None,
    ) -> str:
        """Generate a high-quality cheatsheet using agentic approach.
        
        Args:
            knowledge: ClusteredKnowledge from clustering module
            title: Title for the cheatsheet
            save_path: Optional path to save the LaTeX file
            
        Returns:
            LaTeX content as string
        """
        
        # Step 1: Analyze knowledge
        print(f"Analyzing knowledge structure...")
        analysis = self._analyze_knowledge(knowledge)
        
        # Step 2: Generate content for each section
        print(f"Generating section content...")
        section_contents = {}
        
        # Group nodes by section (or difficulty level as fallback)
        sections = analysis.get("sections", ["Fundamentals", "Core Concepts", "Advanced"])
        
        # Simple assignment: distribute nodes across sections by difficulty
        nodes_by_difficulty = {}
        for node in knowledge.nodes:
            diff = knowledge.node_to_difficulty.get(node.node_id)
            level = diff.level if diff else 0
            if level not in nodes_by_difficulty:
                nodes_by_difficulty[level] = []
            nodes_by_difficulty[level].append(node)
        
        for i, section in enumerate(sections):
            # Get nodes for this section (round-robin)
            section_nodes = []
            for level in sorted(nodes_by_difficulty.keys()):
                if i < len(nodes_by_difficulty[level]):
                    section_nodes.append(nodes_by_difficulty[level][i])
            
            if section_nodes:
                section_contents[section] = self._generate_section_content(
                    section, section_nodes, knowledge
                )
        
        # Step 3: Build final document
        print(f"Building LaTeX document...")
        latex_content = self._build_latex_document(
            title, analysis, section_contents, knowledge
        )
        
        # Step 4: Optional refinement (simplified for now)
        # In production, could add iterative refinement here
        
        # Step 5: Save if requested
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(latex_content)
            print(f"Saved to {save_path}")
        
        return latex_content


def generate_agentic_cheatsheet(
    knowledge: ClusteredKnowledge,
    title: str = "Study Cheatsheet",
    model: str = "gpt-4-turbo-preview",
    save_path: Optional[str | Path] = None,
) -> str:
    """Convenience function to generate cheatsheet with default settings.
    
    Args:
        knowledge: ClusteredKnowledge from clustering module
        title: Cheatsheet title
        model: LLM model to use
        save_path: Optional path to save output
        
    Returns:
        LaTeX content as string
    """
    
    generator = AgenticCheatsheetGenerator(model=model)
    return generator.generate(knowledge, title=title, save_path=save_path)

from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
import pickle as pkl
import pymupdf
import pymupdf.layout
import pymupdf4llm

from dotenv import load_dotenv

from backend.agents.types import PageContent, ImportantCategory

# Suppress pypdf warnings about corrupted objects
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")

load_dotenv()

@dataclass(frozen=True)
class ParseOptions:
    model: str = "gpt-4o-mini"
    min_chars_per_page: int = 30


def json_to_pages_dict(pdf_json: dict) -> dict[int, str]:
    """Convert detailed PDF JSON to simplified page_number -> content format.
    
    Args:
        pdf_json: JSON object with structure: {pages: [{page_number, fulltext: [{lines: [{spans: [{text}]}]}]}]}
        
    Returns:
        Dict mapping page_number (int) to concatenated text content (str)
    """
    pages_dict = {}
    
    pages_list = pdf_json.get("pages", [])
    for page_obj in pages_list:
        page_number = page_obj.get("page_number")
        if page_number is None:
            continue
        
        # Extract all text from fulltext sections
        text_content = []
        fulltext = page_obj.get("fulltext", [])
        
        for block in fulltext:
            lines = block.get("lines", [])
            for line in lines:
                spans = line.get("spans", [])
                for span in spans:
                    text = span.get("text", "").strip()
                    if text:
                        text_content.append(text)
        
        # Join all text with spaces and clean up
        page_text = " ".join(text_content).strip()
        if page_text:
            pages_dict[page_number] = page_text
    
    return pages_dict


def convert_pdf_to_json(
    source_path: str | Path,
    ) -> Dict[int, str]:
    """Convert PDF to markdown using pypdf and markdownify."""
    doc = pymupdf.open(source_path)
    json_data = pymupdf4llm.to_json(doc)
    json_data = json.loads(json_data)
    print(type(json_data))
    return json_data


def parse_pdf(
    source_path: str | Path,
    category: ImportantCategory,
    out_image_dir: str | Path,
    doc_id_prefix: str | None = None,
    options: ParseOptions | None = None,
) -> List[PageContent]:
    """Parse PDF by sending directly to OpenAI as a document input.

    LLM processes entire PDF, extracts text, corrects typos,
    merges related pages, and filters unimportant content.

    Returns a list of PageContent objects from grouped/merged pages.
    """
    options = options or ParseOptions()
    p = Path(source_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")

    doc_id_prefix = doc_id_prefix or p.stem
    out_image_dir = Path(out_image_dir)
    out_image_dir.mkdir(parents=True, exist_ok=True)

    # Read PDF file
    try:
        print("[Parser] Converting PDF to JSON...")
        json_data = convert_pdf_to_json(source_path)
        print("[Parser] PDF conversion complete.")
    except Exception as e:
        print(f"[Parser] Error reading PDF {p}: {e}")
        return []

    # Call OpenAI with PDF document
    try:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[Parser] OPENAI_API_KEY not set, cannot process with LLM")
            return []

        client = OpenAI(api_key=api_key)

        transformed_json_data = json_to_pages_dict(json_data)

        prompt = f"""You are an expert Cheatsheet Content Extractor. Process the provided per-page content (as JSON) to isolate high-signal, examinable material.

Tasks:
1. Identify logical page groups (consecutive pages covering the same core concept).
2. Extract ONLY the core technical content, definitions, formulas, and explanations.
3. Aggressively filter out non-examinable metadata: lecturer names, course codes, office hours, syllabus outlines, administrative announcements, title slides, acknowledgments, and repetitive headers/footers.
4. Merge pages that are topically related.
5. Return SKIP for any page group that lacks technical substance (e.g., purely administrative pages, title pages, or course logistics).

Return ONLY a valid JSON object:
{{
  "page_groups": [
    {{"pages": [1, 2], "content": "Cleaned, typo-corrected technical text...", "topic": "Topic label"}},
    {{"pages": [3], "content": "SKIP", "topic": "Administrative/Title"}}
  ]
}}

Rules:
- IF content is purely administrative (Course intro, Lecturer bio, Grading criteria), set content to "SKIP".
- Remove all "housekeeping" text (e.g., "Any questions?", "Next week we will cover...").
- Correct all typos and spelling mistakes.
- Merge consecutive pages about the same topic.
- Content string must be dense and fact-focused, ready for summarization.
- Return ONLY the JSON, no markdown or explanation.

Per-page content (keys are page numbers, values are the page text; use these page numbers in your output):
```json
{transformed_json_data}
```
"""

        try:
            response = client.responses.create(
                model=options.model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }],
                temperature=0.0,
                max_output_tokens=4000,
            )

            response_text = (getattr(response, "output_text", None) or "").strip()
            if not response_text:
                # Fallback if SDK version doesn’t expose output_text for some reason
                response_text = ""
                try:
                    for item in response.output:
                        if item.type == "message":
                            for c in item.content:
                                if c.type == "output_text":
                                    response_text += c.text
                    response_text = response_text.strip()
                except Exception:
                    pass

        except Exception as e:
            print(f"[Parser] LLM API call failed: {e}")
            return []

        # Parse JSON response (keep your existing robustness)
        try:
            # Strip common fences if the model misbehaves
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            extracted_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[Parser] Failed to parse LLM JSON response: {e}")
            print(f"[Parser] Raw response (truncated): {response_text[:500]}")
            return []

        # Convert page groups to PageContent objects (same as your code)
        pages: List[PageContent] = []
        for group in extracted_data.get("page_groups", []):
            content = (group.get("content") or "").strip()
            if not content or content.upper() == "SKIP":
                continue

            page_nums = group.get("pages", [])
            topic = group.get("topic", "Unknown")
            first_page = page_nums[0] if page_nums else 0

            if len(page_nums) > 1:
                page_range = f"p{page_nums[0]}-{page_nums[-1]}"
            else:
                page_range = f"p{first_page}"

            doc_id = f"{doc_id_prefix}_{page_range}"

            # NOTE: you currently don’t store `topic` in PageContent (unless it has a field).
            # If PageContent supports extra fields, you can attach it; otherwise we keep identical behavior.
            pages.append(
                PageContent(
                    doc_id=doc_id,
                    source_path=str(p.resolve()),
                    category=category,
                    page=first_page,
                    text=content,
                    images=[],
                )
            )

        print(f"[Parser] Extracted {len(pages)} page groups from {p.name}")

        with open(f"test_data/pages_{Path(source_path).stem}.pkl", "wb") as f:
            pkl.dump(pages, f)

        with open(f"test_data/test_json_folder/json_{Path(source_path).stem}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(transformed_json_data, indent = 2))

        return pages

    except Exception as e:
        print(f"[Parser] LLM extraction failed for {p}: {e}")
        return []
    
# def parse_pdf(
#     source_path: str | Path,
#     category: ImportantCategory,
#     out_image_dir: str | Path,
#     doc_id_prefix: str | None = None,
#     options: ParseOptions | None = None,
# ) -> List[PageContent]:
    
#     with open(f"test_data/pages_{Path(source_path).stem}.pkl", "rb") as f:
#         pages = pkl.load(f)
#     return pages
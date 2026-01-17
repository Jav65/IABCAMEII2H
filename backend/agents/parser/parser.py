from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import List
import pickle as pkl

from dotenv import load_dotenv

from backend.agents.types import PageContent, ImportantCategory

# Suppress pypdf warnings about corrupted objects
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")

load_dotenv()

@dataclass(frozen=True)
class ParseOptions:
    model: str = "gpt-4o-mini"
    min_chars_per_page: int = 30


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
        pdf_bytes = p.read_bytes()
        print(f"[Parser] Read PDF {p.name} ({len(pdf_bytes)} bytes)")
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

        # Upload PDF (upload step is only storage; prompt goes in the model call)
        try:
            with open(p, "rb") as f:
                file_response = client.files.create(
                    file=f,
                    purpose="user_data",  # better for model inputs than "assistants"
                )
            file_id = file_response.id
            print(f"[Parser] Uploaded PDF to OpenAI, file_id: {file_id}")
        except Exception as e:
            print(f"[Parser] Failed to upload PDF to OpenAI: {e}")
            return []

        prompt = """You are an expert Cheatsheet Content Extractor. Process this PDF document to isolate high-signal, examinable material.

Tasks:
1. Identify logical page groups (consecutive pages covering the same core concept).
2. Extract ONLY the core technical content, definitions, formulas, and explanations.
3. Aggressively filter out non-examinable metadata: lecturer names, course codes, office hours, syllabus outlines, administrative announcements, title slides, acknowledgments, and repetitive headers/footers.
4. Merge pages that are topically related.
5. Return SKIP for any page group that lacks technical substance (e.g., purely administrative pages, title pages, or course logistics).

Return ONLY a valid JSON object:
{
  "page_groups": [
    {"pages": [1, 2], "content": "Cleaned, typo-corrected technical text...", "topic": "Topic label"},
    {"pages": [3], "content": "SKIP", "topic": "Administrative/Title"}
  ]
}

Rules:
- IF content is purely administrative (Course intro, Lecturer bio, Grading criteria), set content to "SKIP".
- Remove all "housekeeping" text (e.g., "Any questions?", "Next week we will cover...").
- Correct all typos and spelling mistakes.
- Merge consecutive pages about the same topic.
- Content string must be dense and fact-focused, ready for summarization.
- Return ONLY the JSON, no markdown or explanation."""

        try:
            # Use Responses API with input_file
            response = client.responses.create(
                model=options.model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_file", "file_id": file_id},
                    ],
                }],
                temperature=0.0,
                max_output_tokens=4000,
            )

            # `output_text` is the simplest way to get the model's text output
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

        finally:
            # Clean up uploaded file
            try:
                client.files.delete(file_id)
                print("[Parser] Cleaned up uploaded file")
            except Exception as e:
                print(f"[Parser] Warning: Could not delete file {file_id}: {e}")

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

        with open("test_data/pages.pkl", "wb") as f:
            pkl.dump(pages, f)

        return pages

    except Exception as e:
        print(f"[Parser] LLM extraction failed for {p}: {e}")
        return []
    
def parse_pdf(
    source_path: str | Path,
    category: ImportantCategory,
    out_image_dir: str | Path,
    doc_id_prefix: str | None = None,
    options: ParseOptions | None = None,
) -> List[PageContent]:
    
    with open("test_data/pages.pkl", "rb") as f:
        pages = pkl.load(f)
    return pages

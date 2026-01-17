from __future__ import annotations

import base64
import json
import os
import re
import warnings
from dotenv import load_dotenv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.types import ImageRef, PageContent, ImportantCategory
from backend.agents.utils.hash import sha256_bytes

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
    """Parse PDF by sending directly to OpenAI as base64 document.
    
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
        with open(p, 'rb') as f:
            pdf_bytes = f.read()
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
        
        # Upload PDF to OpenAI Files API
        try:
            with open(p, 'rb') as f:
                file_response = client.files.create(
                    file=(p.name, f, "application/pdf"),
                    purpose="assistants"
                )
            file_id = file_response.id
            print(f"[Parser] Uploaded PDF to OpenAI, file_id: {file_id}")
        except Exception as e:
            print(f"[Parser] Failed to upload PDF to OpenAI: {e}")
            return []
        
        try:
            # Send request with file reference
            response = client.chat.completions.create(
                model=options.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are a document extraction and analysis system. Process this PDF document.

Tasks:
1. Identify logical page groups (consecutive pages covering same topic)
2. Extract text from each group, correcting ALL typos and spelling errors
3. Merge pages that are topically related
4. Skip pages that are unimportant (blank, pure formatting, page numbers, footers only)
5. Return SKIP for any page group that contains only unimportant information

Return ONLY a valid JSON object:
{
  "page_groups": [
    {"pages": [1, 2], "content": "Extracted text with typos corrected", "topic": "Topic label"},
    {"pages": [3], "content": "SKIP"}
  ]
}

Rules:
- If content is unimportant, set content to "SKIP"
- Correct all typos and spelling mistakes
- Merge consecutive pages about the same topic
- Each group must have pages list, content, and topic
- Return ONLY the JSON, no markdown or explanation"""
                        },
                        {
                            "type": "file",
                            "file": file_id
                        }
                    ]
                }],
                temperature=0.0,
                max_tokens=4000,
            )
            
            response_text = response.choices[0].message.content.strip()
        finally:
            # Clean up: delete the uploaded file
            try:
                client.files.delete(file_id)
                print(f"[Parser] Cleaned up uploaded file")
            except Exception as e:
                print(f"[Parser] Warning: Could not delete file {file_id}: {e}")
        
        # Parse JSON response
        try:
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[Parser] Failed to parse LLM JSON response: {e}")
            return []
        
        # Convert page groups to PageContent objects
        pages: List[PageContent] = []
        for group in extracted_data.get("page_groups", []):
            content = group.get("content", "")
            
            # Skip unimportant pages
            if content.upper() == "SKIP" or not content.strip():
                continue
            
            page_nums = group.get("pages", [])
            topic = group.get("topic", "Unknown")
            first_page = page_nums[0] if page_nums else 0
            
            # Create doc_id from page range
            if len(page_nums) > 1:
                page_range = f"p{page_nums[0]}-{page_nums[-1]}"
            else:
                page_range = f"p{first_page}"
            
            doc_id = f"{doc_id_prefix}_{page_range}"
            
            pages.append(
                PageContent(
                    doc_id=doc_id,
                    source_path=str(p.resolve()),
                    category=category,
                    page=first_page,
                    text=content.strip(),
                    images=[],
                )
            )
        
        print(f"[Parser] Extracted {len(pages)} page groups from {p.name}")
        return pages
        
    except Exception as e:
        print(f"[Parser] LLM extraction failed for {p}: {e}")
        return []



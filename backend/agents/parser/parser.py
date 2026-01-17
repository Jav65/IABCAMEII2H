from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import fitz  # PyMuPDF

from backend.agents.types import ImageRef, PageContent, ImportantCategory
from backend.agents.utils.hash import sha256_bytes


_whitespace_re = re.compile(r"[\t\f\v ]+")


def _clean_text(text: str) -> str:
    # keep newlines (useful for headings / structure), but normalize runs of spaces
    text = _whitespace_re.sub(" ", text)
    # collapse >2 newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass(frozen=True)
class ParseOptions:
    save_images: bool = True
    min_chars_per_page: int = 30
    image_output_ext: str = "png"  # 'png' is safe and lossless


def parse_pdf(
    source_path: str | Path,
    category: ImportantCategory,
    out_image_dir: str | Path,
    doc_id_prefix: str | None = None,
    options: ParseOptions | None = None,
) -> List[PageContent]:
    """Parse a PDF into per-page text + extracted images.

    Returns a list of PageContent objects, preserving provenance (file + page).
    """
    options = options or ParseOptions()
    p = Path(source_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")

    out_image_dir = Path(out_image_dir)
    out_image_dir.mkdir(parents=True, exist_ok=True)

    doc_id_prefix = doc_id_prefix or p.stem

    pages: List[PageContent] = []
    with fitz.open(p) as doc:
        for i, page in enumerate(doc):
            page_no = i + 1  # human-friendly
            text = _clean_text(page.get_text("text") or "")

            images: List[ImageRef] = []
            if options.save_images:
                for img in page.get_images(full=True):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    try:
                        # Robustly convert unsupported colorspaces to RGB before saving.
                        # Many PDFs contain CMYK or other colorspaces that Pillow/PyMuPDF
                        # cannot write directly to PNG; converting to RGB avoids
                        # "unsupported colorspace" errors.
                        if pix.n != 3:
                            try:
                                rgb = fitz.Pixmap(fitz.csRGB, pix)
                            except Exception:
                                # Fallback: attempt the same conversion again; if it fails,
                                # re-raise to surface the original problem.
                                rgb = fitz.Pixmap(fitz.csRGB, pix)
                            # Use the converted pixmap for saving
                            save_pix = rgb
                        else:
                            save_pix = pix

                        img_bytes = save_pix.tobytes(options.image_output_ext)
                        image_id = sha256_bytes(img_bytes)[:16]
                        out_path = out_image_dir / f"{doc_id_prefix}_p{page_no}_{image_id}.{options.image_output_ext}"
                        out_path.write_bytes(img_bytes)
                        images.append(
                            ImageRef(
                                image_id=image_id,
                                file_path=str(out_path.resolve()),
                                page=page_no,
                                width=save_pix.width,
                                height=save_pix.height,
                                ext=options.image_output_ext,
                            )
                        )
                    finally:
                        # Help GC: explicitly clear Pixmap refs
                        try:
                            pix = None
                        except Exception:
                            pass
                        try:
                            save_pix = None
                        except Exception:
                            pass

            # skip nearly-empty pages to reduce noise for the KG extractor
            if len(text) < options.min_chars_per_page and not images:
                continue

            pages.append(
                PageContent(
                    doc_id=f"{doc_id_prefix}_p{page_no}",
                    source_path=str(p.resolve()),
                    category=category,
                    page=page_no,
                    text=text,
                    images=images,
                )
            )

    return pages


def refine_pages_with_llm(pages: List[PageContent], model: str | None = None, use_llm: bool = True) -> List[PageContent]:
    """
    Refine raw PageContent objects using an LLM and heuristics.

    Steps:
    1. (Optional) Call LLM per page to remove unimportant text/images.
    2. Heuristic merging: merge consecutive pages with high token overlap.

    Returns a new list of PageContent objects where some pages may be combined.
    """
    # Simple local cleaning helper
    def _local_clean(text: str) -> str:
        # Remove long runs of whitespace and obvious headers/footers lines
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # drop lines that look like page numbers or footers
        cleaned = []
        for ln in lines:
            if re.match(r"^page\s+\d+$", ln.lower()):
                continue
            if len(ln) < 3:
                continue
            cleaned.append(ln)
        return "\n".join(cleaned)

    # Try to get an OpenAI-compatible client
    client = None
    if use_llm:
        try:
            from openai import OpenAI
            import os
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                client = OpenAI(api_key=api_key)
        except Exception:
            client = None

    refined_texts: List[str] = []
    for page in pages:
        text = page.text or ""
        if client:
            try:
                prompt = (
                    "You are given the text of a single page from an academic document. "
                    "Return a cleaned, concise version that removes unimportant words and noise, "
                    "drops irrelevant images (just omit them), and preserves key facts and definitions. "
                    "Output only the cleaned text.\n\nPage text:\n" + text[:8000]
                )
                resp = client.chat.completions.create(
                    model=model or "gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=1200,
                )
                cleaned = resp.choices[0].message.content.strip()
            except Exception:
                cleaned = _local_clean(text)
        else:
            cleaned = _local_clean(text)
        refined_texts.append(cleaned)

    # Merge consecutive pages if overlap ratio is high
    def _token_set(s: str):
        toks = [t.lower() for t in re.findall(r"\w+", s) if len(t) > 2]
        return set(toks)

    refined_pages: List[PageContent] = []
    i = 0
    while i < len(pages):
        combined_from = [pages[i].doc_id]
        combined_text = refined_texts[i]
        combined_images = list(pages[i].images)

        j = i + 1
        while j < len(pages):
            a = _token_set(combined_text)
            b = _token_set(refined_texts[j])
            if not a or not b:
                overlap = 0.0
            else:
                overlap = len(a & b) / max(len(a | b), 1)
            # merge threshold: 0.25 (empirical)
            if overlap >= 0.25:
                combined_from.append(pages[j].doc_id)
                combined_text = combined_text + "\n\n" + refined_texts[j]
                combined_images.extend(pages[j].images)
                j += 1
            else:
                break

        # create new PageContent-like object (keep PageContent dataclass)
        first = pages[i]
        new_doc_id = f"{first.doc_id}_combined_{'_'.join([c.split('_')[-1] for c in combined_from])}"
        refined_pages.append(
            PageContent(
                doc_id=new_doc_id,
                source_path=first.source_path,
                category=first.category,
                page=first.page,
                text=combined_text.strip(),
                images=combined_images,
            )
        )

        i = j

    return refined_pages

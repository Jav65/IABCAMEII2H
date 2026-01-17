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

from __future__ import annotations

import io

import pypdf


def format_pages(pages: list[str | None]) -> str:
    blocks = []
    for i, text in enumerate(pages, start=1):
        if text and text.strip():
            blocks.append(f"--- Page {i} ---\n{text}")
    return "\n\n".join(blocks)


def first_pages_text(pdf_bytes: bytes, n: int = 3) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str | None] = []
    for page in reader.pages[:n]:
        pages.append(page.extract_text())
    return format_pages(pages)

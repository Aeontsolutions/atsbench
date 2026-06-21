"""One-time prep: build the committed classification dataset from local PDFs.

Usage: uv run python fixtures/classification/build.py /tmp/jse/golden_dataset_documents /tmp/symbols.json
Outputs fixtures/classification/dataset.jsonl and MANIFEST.md, and interpolates
the symbol reference into system_prompt.txt. PDFs are NOT committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from atsbench.fixtures.filename_labels import parse_filename
from atsbench.fixtures.pdf_text import first_pages_text

HERE = Path(__file__).resolve().parent


def main(pdf_dir: str, symbols_json: str) -> None:
    symbols = json.loads(Path(symbols_json).read_text())
    known = {s.upper() for s in symbols}
    records, excluded = [], []

    for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
        labels = parse_filename(pdf.name, known)
        if labels is None:
            excluded.append(pdf.name)
            continue
        try:
            text = first_pages_text(pdf.read_bytes(), n=3)
        except Exception as e:  # corrupt/encrypted PDF -> exclude, don't crash
            excluded.append(f"{pdf.name} (text extraction failed: {e})")
            continue
        if not text.strip():
            excluded.append(f"{pdf.name} (no extractable text in first 3 pages)")
            continue
        records.append({
            "id": pdf.stem,
            "input_text": text,
            "golden": asdict(labels),
            "source_filename": pdf.name,
            "sensitivity": "public",
        })

    out = HERE / "dataset.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    digest = hashlib.sha256(out.read_bytes()).hexdigest()[:16]
    (HERE / "MANIFEST.md").write_text(
        f"# Classification fixture manifest\n\n"
        f"- records: {len(records)} / {len(records) + len(excluded)} PDFs\n"
        f"- dataset.jsonl sha256: {digest}\n"
        f"- source: Aeontsolutions/jse-doc-workflows golden_dataset_documents\n"
        f"- input: first 3 pages text (pypdf); labels derived from filenames\n\n"
        f"## Excluded ({len(excluded)})\n" + "\n".join(f"- {e}" for e in excluded) + "\n"
    )

    # interpolate the symbol reference into the system prompt
    ref = "\n".join(f"{s} — {name}" for s, name in sorted(symbols.items()))
    sp = HERE / "system_prompt.txt"
    sp.write_text(sp.read_text().replace("{_INSTRUMENT_SYMBOL_REFERENCE}", ref))

    print(f"wrote {len(records)} records, excluded {len(excluded)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
